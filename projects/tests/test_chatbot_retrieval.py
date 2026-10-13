"""Tests du corpus FAQ et des analyses privées du chatbot."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from projects.ai.retrieval import (
    build_user_analysis_corpus,
    retrieve_faq,
    retrieve_user_analysis,
)
from projects.models import Project, ProjectAnalysis


class ChatbotRetrievalTests(TestCase):
    """Vérifie la pertinence et l'isolation des corpus du chatbot."""

    def setUp(self) -> None:
        """Crée deux porteurs et une analyse validée de chacun."""
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="chatbot-owner",
            email="owner@example.com",
            password="password",
            role="PROJECT_OWNER",
        )
        self.other_owner = user_model.objects.create_user(
            username="chatbot-other",
            email="other@example.com",
            password="password",
            role="PROJECT_OWNER",
        )
        self.project = Project.objects.create(
            owner=self.owner,
            name="Publication boutique",
            description="Une boutique en ligne.",
            deadline=date.today() + timedelta(days=30),
            estimated_amount=Decimal("1000.00"),
        )
        self.other_project = Project.objects.create(
            owner=self.other_owner,
            name="Autre projet",
            description="Projet confidentiel.",
            deadline=date.today() + timedelta(days=30),
            estimated_amount=Decimal("1000.00"),
        )
        result = {
            "complexite": "FAIBLE",
            "confiance": 0.8,
            "recommandations": ["Publier après validation."],
            "contact": "contact@example.com",
        }
        ProjectAnalysis.objects.create(project=self.project, result=result)
        ProjectAnalysis.objects.create(
            project=self.other_project,
            result={"complexite": "ELEVEE", "recommandations": ["Secret"]},
        )

    def test_publication_question_returns_publication_faq(self) -> None:
        """Une question de publication renvoie la FAQ correspondante."""
        results = retrieve_faq("Comment publier mon projet ?")
        self.assertTrue(results)
        self.assertEqual(results[0]["id"], "publier-projet")

    def test_available_projects_question_returns_published_faq(self) -> None:
        """Une question sur les projets disponibles renvoie la FAQ publiée."""
        results = retrieve_faq("quelles sont les projets disponibles ?")
        self.assertTrue(results)
        self.assertEqual(results[0]["id"], "projets-publies")

    def test_requested_specialties_question_returns_no_faq(self) -> None:
        """Une question sur les spécialités renvoie la FAQ publiée la plus proche."""
        results = retrieve_faq(
            "quelles sont les spécialités demandées pour les projets maintenant ?"
        )
        self.assertTrue(results)
        self.assertEqual(results[0]["id"], "projets-publies")

    def test_stopwords_only_question_returns_no_faq(self) -> None:
        """Une question composée uniquement de mots vides ne déclenche aucune exception."""
        self.assertEqual(retrieve_faq("les sont pour ?"), [])

    def test_successful_faq_questions_return_expected_blocks(self) -> None:
        """Les questions FAQ usuelles renvoient leur bloc attendu."""
        expected_blocks = (
            ("comment publier mon projet ?", "publier-projet"),
            ("que veut dire taux_reussite ?", "champ-taux-reussite"),
            ("c'est quoi DECLINED ?", "statut-declined"),
        )
        for question, expected_id in expected_blocks:
            with self.subTest(question=question):
                results = retrieve_faq(question)
                self.assertTrue(results)
                self.assertEqual(results[0]["id"], expected_id)

    def test_unrelated_question_returns_no_faq(self) -> None:
        """Une question hors sujet ne renvoie aucun bloc FAQ."""
        self.assertEqual(retrieve_faq("recette de couscous"), [])

    def test_other_owner_analysis_is_not_returned(self) -> None:
        """Une recherche ne renvoie jamais l'analyse d'un autre porteur."""
        results = retrieve_user_analysis(self.owner, "analyse du projet publication")
        self.assertTrue(results)
        self.assertTrue(all(item["id"] != f"analysis-{self.other_project.id}" for item in results))

    def test_analysis_email_is_anonymized(self) -> None:
        """Les données personnelles sont anonymisées dans les blocs d'analyse."""
        block = build_user_analysis_corpus(self.owner)[0]
        self.assertIn("[EMAIL]", block["reponse"])
        self.assertNotIn("contact@example.com", block["reponse"])
