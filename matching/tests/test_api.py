"""Tests des endpoints du module matching."""

import json
from unittest.mock import patch

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from projects.models import Project
from users.models import User

from matching.models import MatchScore, Recommendation

from .factories import (
    make_analysis,
    make_freelancer,
    make_owner,
    make_project,
    make_quiz_attempt,
)

SEMANTIC_PAYLOAD = json.dumps(
    {
        "score_semantique": 90,
        "concepts_correspondants": ["Python"],
        "competences_pertinentes": ["Django"],
        "justification": "Profil aligné sur le besoin back-end.",
    }
)


class MatchingApiTests(APITestCase):
    """Parcours complet des endpoints du matching."""

    def setUp(self):
        """Prépare un porteur, un projet analysé et deux freelances."""
        self.owner = make_owner("apiowner")
        self.project = make_project(self.owner)
        make_analysis(self.project)
        self.strong = make_freelancer(
            "strong", skills=["Python", "Django"], hourly_rate=30
        )
        self.weak = make_freelancer(
            "weak", skills=["Comptabilité"], hourly_rate=200
        )

    def authenticate(self, user: User) -> None:
        """Authentifie le client de test."""
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # --- Recommandations de freelances -------------------------------------

    def test_freelancers_are_ranked_by_score(self):
        """Le freelance le plus pertinent est classé en premier."""
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(results[0]["freelancer_id"], self.strong.pk)
        self.assertGreater(results[0]["total_score"], results[-1]["total_score"])

    def test_response_contains_explainable_breakdown(self):
        """Chaque recommandation expose ses sous-scores et ses explications."""
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        first = response.json()["results"][0]
        self.assertEqual(
            sorted(first["subscores"]), ["budget", "level", "quiz", "skills"]
        )
        self.assertTrue(first["explanations"])
        self.assertEqual(first["mode"], "DETERMINISTIC")

    def test_pagination_is_applied(self):
        """La pagination limite le nombre de résultats par page."""
        for index in range(12):
            make_freelancer(f"bulk{index}")
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/?page_size=5"
        )
        payload = response.json()
        self.assertEqual(len(payload["results"]), 5)
        self.assertIsNotNone(payload["next"])
        self.assertGreaterEqual(payload["count"], 14)

    def test_invalid_semantic_parameter_is_rejected(self):
        """Un paramètre booléen invalide retourne une erreur de validation."""
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/?semantic=peut-etre"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_limit_parameter_is_rejected(self):
        """Une limite hors bornes retourne une erreur de validation."""
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/?limit=9999"
        )
        self.assertEqual(response.status_code, 400)

    def test_semantic_mode_uses_the_llm_and_marks_hybrid(self):
        """Le mode sémantique bascule le score en mode hybride."""
        self.authenticate(self.owner)
        with patch(
            "matching.services.semantic_matching.call_llm",
            return_value=SEMANTIC_PAYLOAD,
        ):
            response = self.client.get(
                f"/api/matching/projects/{self.project.pk}/freelancers/?semantic=true"
            )
        first = response.json()["results"][0]
        self.assertEqual(first["mode"], "HYBRID")
        self.assertEqual(first["semantic_score"], 90.0)

    def test_llm_failure_falls_back_without_breaking_the_api(self):
        """Une panne du LLM laisse l'API répondre en mode déterministe."""
        self.authenticate(self.owner)
        with patch(
            "matching.services.semantic_matching.call_llm",
            side_effect=RuntimeError("panne"),
        ):
            response = self.client.get(
                f"/api/matching/projects/{self.project.pk}/freelancers/?semantic=true"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["mode"], "DETERMINISTIC")

    # --- Persistance -------------------------------------------------------

    def test_refresh_persists_scores(self):
        """Le recalcul enregistre un score par freelance évalué."""
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/matching/projects/{self.project.pk}/refresh/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()["stored"], 0)
        self.assertTrue(MatchScore.objects.filter(project=self.project).exists())

    def test_refresh_is_idempotent_on_the_same_pair(self):
        """Deux recalculs ne créent pas de doublon de score."""
        self.authenticate(self.owner)
        self.client.post(f"/api/matching/projects/{self.project.pk}/refresh/")
        first_count = MatchScore.objects.filter(project=self.project).count()
        self.client.post(f"/api/matching/projects/{self.project.pk}/refresh/")
        self.assertEqual(
            MatchScore.objects.filter(project=self.project).count(), first_count
        )

    def test_scores_endpoint_returns_persisted_rows(self):
        """L'endpoint des scores relit les lignes enregistrées."""
        self.authenticate(self.owner)
        self.client.post(f"/api/matching/projects/{self.project.pk}/refresh/")
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/scores/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()["count"], 0)

    # --- Matching inverse --------------------------------------------------

    def test_freelancer_feed_lists_published_projects(self):
        """Le freelance reçoit les projets publiés et analysés."""
        self.authenticate(self.strong)
        response = self.client.get("/api/matching/recommended-projects/")
        self.assertEqual(response.status_code, 200)
        ids = [item["project_id"] for item in response.json()["results"]]
        self.assertEqual(ids, [self.project.pk])

    def test_unpublished_projects_are_filtered_out(self):
        """Un projet non publié n'est jamais recommandé à un freelance."""
        draft = make_project(self.owner, status=Project.Status.DRAFT, name="Brouillon")
        make_analysis(draft)
        self.authenticate(self.strong)
        response = self.client.get("/api/matching/recommended-projects/")
        ids = [item["project_id"] for item in response.json()["results"]]
        self.assertNotIn(draft.pk, ids)

    def test_project_without_analysis_is_filtered_out(self):
        """Un projet publié sans analyse exploitable est ignoré."""
        published = make_project(self.owner, name="Sans analyse")
        self.authenticate(self.strong)
        response = self.client.get("/api/matching/recommended-projects/")
        ids = [item["project_id"] for item in response.json()["results"]]
        self.assertNotIn(published.pk, ids)

    def test_feed_uses_quiz_results_of_the_caller(self):
        """Les quiz du freelance connecté influencent son score."""
        self.authenticate(self.strong)
        before = self.client.get("/api/matching/recommended-projects/").json()
        make_quiz_attempt(self.strong, "python", 100)
        after = self.client.get("/api/matching/recommended-projects/").json()
        self.assertNotEqual(
            before["results"][0]["match"]["total_score"],
            after["results"][0]["match"]["total_score"],
        )

    # --- Recommandations ---------------------------------------------------

    def test_owner_can_invite_a_validated_freelancer(self):
        """Le porteur peut inviter un freelance validé."""
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/matching/projects/{self.project.pk}/recommendations/",
            {"freelancer_id": self.strong.pk, "speciality": "Python"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "PROPOSED")

    def test_owner_cannot_invite_an_unvalidated_freelancer(self):
        """Un freelance non validé ne peut pas être invité."""
        pending = make_freelancer(
            "pendinginvite", moderation_status=User.ModerationStatus.PENDING
        )
        self.authenticate(self.owner)
        response = self.client.post(
            f"/api/matching/projects/{self.project.pk}/recommendations/",
            {"freelancer_id": pending.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_freelancer_responds_to_its_own_recommendation(self):
        """Le freelance destinataire peut accepter sa recommandation."""
        recommendation = Recommendation.objects.create(
            project=self.project, freelancer=self.strong
        )
        self.authenticate(self.strong)
        response = self.client.post(
            f"/api/matching/recommendations/{recommendation.pk}/respond/",
            {"decision": "accept"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ACCEPTED")

    def test_freelancer_cannot_respond_for_someone_else(self):
        """Un freelance ne peut pas répondre à la place d'un autre."""
        recommendation = Recommendation.objects.create(
            project=self.project, freelancer=self.strong
        )
        self.authenticate(self.weak)
        response = self.client.post(
            f"/api/matching/recommendations/{recommendation.pk}/respond/",
            {"decision": "accept"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_second_response_is_rejected(self):
        """Une recommandation déjà traitée refuse une seconde réponse."""
        recommendation = Recommendation.objects.create(
            project=self.project, freelancer=self.strong
        )
        self.authenticate(self.strong)
        self.client.post(
            f"/api/matching/recommendations/{recommendation.pk}/respond/",
            {"decision": "accept"},
            format="json",
        )
        response = self.client.post(
            f"/api/matching/recommendations/{recommendation.pk}/respond/",
            {"decision": "decline"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_invalid_decision_is_rejected(self):
        """Une décision hors énumération est refusée."""
        recommendation = Recommendation.objects.create(
            project=self.project, freelancer=self.strong
        )
        self.authenticate(self.strong)
        response = self.client.post(
            f"/api/matching/recommendations/{recommendation.pk}/respond/",
            {"decision": "peut-etre"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_freelancer_only_sees_its_own_recommendations(self):
        """Le fil des recommandations est limité à l'appelant."""
        Recommendation.objects.create(project=self.project, freelancer=self.weak)
        self.authenticate(self.strong)
        response = self.client.get("/api/matching/recommendations/")
        self.assertEqual(response.json()["count"], 0)
