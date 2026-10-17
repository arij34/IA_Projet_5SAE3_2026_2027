"""Tests des règles d'accès serveur du module matching."""

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from projects.models import Project
from users.models import User

from .factories import make_analysis, make_freelancer, make_owner, make_project


class PermissionTests(APITestCase):
    """Contrôles de rôle, de modération et de propriété."""

    def setUp(self):
        """Prépare deux porteurs, un freelance et un projet analysé."""
        self.owner = make_owner("owner1")
        self.other_owner = make_owner("owner2")
        self.freelancer = make_freelancer("freelance1")
        self.project = make_project(self.owner)
        make_analysis(self.project)

    def authenticate(self, user: User) -> None:
        """Authentifie le client de test avec le jeton de l'utilisateur."""
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_anonymous_is_rejected(self):
        """Un appel anonyme ne peut pas lire les recommandations."""
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        self.assertIn(response.status_code, (401, 403))

    def test_freelancer_cannot_read_project_recommendations(self):
        """Un freelance ne peut pas consulter les candidats d'un projet."""
        self.authenticate(self.freelancer)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_cannot_read_another_owner_project(self):
        """Un porteur ne peut pas accéder au projet d'un autre porteur."""
        self.authenticate(self.other_owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_cannot_refresh_another_owner_project(self):
        """Le recalcul est lui aussi réservé au propriétaire du projet."""
        self.authenticate(self.other_owner)
        response = self.client.post(
            f"/api/matching/projects/{self.project.pk}/refresh/"
        )
        self.assertEqual(response.status_code, 404)

    def test_pending_owner_is_rejected(self):
        """Un porteur en attente de modération est refusé."""
        self.owner.moderation_status = User.ModerationStatus.PENDING
        self.owner.save(update_fields=("moderation_status",))
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_cannot_read_freelancer_feed(self):
        """Un porteur ne peut pas lire le fil réservé aux freelances."""
        self.authenticate(self.owner)
        response = self.client.get("/api/matching/recommended-projects/")
        self.assertEqual(response.status_code, 403)

    def test_suspect_freelancer_cannot_read_feed(self):
        """Un freelance suspect perd l'accès à ses recommandations."""
        self.freelancer.moderation_status = User.ModerationStatus.SUSPECT
        self.freelancer.save(update_fields=("moderation_status",))
        self.authenticate(self.freelancer)
        response = self.client.get("/api/matching/recommended-projects/")
        self.assertEqual(response.status_code, 403)

    def test_analysis_is_required_before_matching(self):
        """Un projet sans analyse réussie refuse le matching."""
        project = make_project(self.owner, status=Project.Status.DRAFT)
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{project.pk}/freelancers/"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "analysis_required")

    def test_unvalidated_freelancer_is_excluded_from_results(self):
        """Un freelance non validé n'apparaît jamais dans les candidats."""
        pending = make_freelancer(
            "pending1", moderation_status=User.ModerationStatus.PENDING
        )
        rejected = make_freelancer(
            "rejected1", moderation_status=User.ModerationStatus.REJETE
        )
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        self.assertEqual(response.status_code, 200)
        returned = {item["freelancer_id"] for item in response.data["results"]}
        self.assertIn(self.freelancer.pk, returned)
        self.assertNotIn(pending.pk, returned)
        self.assertNotIn(rejected.pk, returned)

    def test_project_owner_is_not_listed_as_candidate(self):
        """Un porteur de projet n'est pas un candidat freelance."""
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        returned = {item["freelancer_id"] for item in response.data["results"]}
        self.assertNotIn(self.owner.pk, returned)

    def test_response_exposes_no_private_fields(self):
        """La réponse n'expose ni e-mail, ni CV, ni statut de modération."""
        self.authenticate(self.owner)
        response = self.client.get(
            f"/api/matching/projects/{self.project.pk}/freelancers/"
        )
        payload = response.json()["results"][0]
        for forbidden in ("email", "cv", "moderation_status", "password"):
            self.assertNotIn(forbidden, payload)
