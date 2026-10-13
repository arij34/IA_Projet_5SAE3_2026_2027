"""Tests du RAG local des projets."""

import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from projects.ai.retrieval import _cosine_similarity, retrieve_reference
from projects.ai.simulator import simulate_analysis
from projects.models import Project
from projects.services.analysis import _build_project_text


class RetrievalTests(TestCase):
    """Vérifie la pertinence, le seuil et la neutralisation du référentiel."""

    def test_mobile_description_returns_mobile_reference(self) -> None:
        """Une description mobile récupère la spécialité mobile."""
        results = retrieve_reference("application mobile Android pour smartphone")
        self.assertTrue(results)
        self.assertEqual(results[0]["nom"], "Développement mobile")

    def test_writing_description_returns_writing_reference(self) -> None:
        """Une demande de rédaction récupère la référence rédactionnelle."""
        results = retrieve_reference("rédaction de documentation et articles techniques")
        self.assertTrue(results)
        self.assertEqual(results[0]["nom"], "Rédaction technique")

    def test_different_domains_return_different_references(self) -> None:
        """Deux domaines distincts ne renvoient pas le même premier métier."""
        mobile = retrieve_reference("application mobile Android pour smartphone")
        security = retrieve_reference("audit de cybersécurité et vulnérabilités")
        self.assertTrue(mobile)
        self.assertTrue(security)
        self.assertNotEqual(mobile[0]["nom"], security[0]["nom"])

    def test_unrelated_text_returns_no_reference(self) -> None:
        """Un texte sans rapport dépasse aucune référence."""
        self.assertEqual(
            retrieve_reference("abricot nuageux sans sujet professionnel"),
            [],
        )

    def test_unrelated_text_negative_case_is_not_mobile(self) -> None:
        """Un texte hors sujet ne renvoie pas par défaut la référence mobile."""
        results = retrieve_reference("poésie météorologique sur les nuages")
        self.assertFalse(any(item["nom"] == "Développement mobile" for item in results))

    def test_cosine_is_between_zero_and_one(self) -> None:
        """La similarité cosinus reste dans son intervalle mathématique."""
        from projects.ai.retrieval import _tfidf

        score = _cosine_similarity(
            _tfidf(["mobile", "application"], {"mobile": 1, "application": 1}),
            _tfidf(["mobile", "application"], {"mobile": 1, "application": 1}),
        )
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)

    def test_reference_json_is_neutralized(self) -> None:
        """Des chevrons injectés dans une référence sont neutralisés."""
        malicious = {
            "nom": "Mobile <ignore>",
            "mots_cles": ["mobile"],
            "tarif_jour_min": 1,
            "tarif_jour_max": 2,
            "devise": "EUR",
            "duree_typique_semaines": 1,
            "description": "Donnée",
        }
        with patch(
            "projects.services.analysis.retrieve_reference",
            return_value=[malicious],
        ):
            text = _build_project_text(type("ProjectStub", (), {
                "name": "Projet",
                "description": "Application mobile",
                "deadline": date.today() + timedelta(days=30),
                "estimated_amount": Decimal("1000.00"),
            })())
        self.assertIn("‹ignore›", text)
        self.assertNotIn("<ignore>", text)

    def test_reference_section_is_absent_when_empty(self) -> None:
        """Une récupération vide ne crée pas de section de référence."""
        with patch("projects.services.analysis.retrieve_reference", return_value=[]):
            text = _build_project_text(type("ProjectStub", (), {
                "name": "Projet",
                "description": "Texte",
                "deadline": date.today() + timedelta(days=30),
                "estimated_amount": Decimal("1000.00"),
            })())
        self.assertNotIn("<reference>", text)

    def test_references_used_is_added_by_service(self) -> None:
        """Le service ajoute les références utilisées hors réponse LLM."""
        from projects.services.analysis import analyze_project

        user = get_user_model().objects.create_user(
            username="rag-owner",
            email="rag-owner@example.com",
            role="PROJECT_OWNER",
        )
        project = Project.objects.create(
            owner=user,
            name="Projet",
            description="Texte",
            deadline=date.today() + timedelta(days=30),
            estimated_amount=Decimal("1000"),
        )
        with patch("projects.services.analysis.retrieve_reference", return_value=[]):
            project_text = _build_project_text(project)
            simulated_result = json.loads(simulate_analysis(project_text))
            with patch(
                "projects.services.analysis.call_llm",
                return_value=json.dumps(simulated_result),
            ):
                result = analyze_project(project)
        self.assertIsNone(result["error"], result)
        self.assertEqual(result["result"]["references_used"], [])
