from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase


User = get_user_model()


class MeApiTests(APITestCase):
    """Teste la consultation et la modification du profil courant."""

    url = "/api/users/me/"

    def setUp(self):
        """Prépare un utilisateur authentifié et un autre utilisateur."""
        self.user = User.objects.create_user(
            username="profil",
            email="profil@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
            title="Ancien titre",
            bio="Ancienne bio",
            skills=["Python"],
            hourly_rate=50,
            moderation_status=User.ModerationStatus.OK,
        )
        self.other_user = User.objects.create_user(
            username="autre",
            email="autre@example.com",
            password="MotDePasseFort!123",
        )
        self.call_llm = patch("users.services.moderation.call_llm")
        self.call_llm_mock = self.call_llm.start()
        self.call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Profil cohérent", "confiance": 0.9}'
        )
        self.addCleanup(self.call_llm.stop)

    def authenticate(self):
        """Authentifie le client avec le jeton de l'utilisateur courant."""
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_get_without_token_returns_401(self):
        """Un utilisateur non authentifié ne peut pas consulter le profil."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_with_token_returns_current_user(self):
        """La réponse GET contient les données de l'utilisateur connecté."""
        self.authenticate()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.id)
        self.assertEqual(response.data["username"], self.user.username)
        self.assertEqual(response.data["email"], self.user.email)

    def test_patch_updates_allowed_profile_fields(self):
        """PATCH enregistre les champs de profil modifiables."""
        self.authenticate()

        response = self.client.patch(
            self.url,
            {
                "title": "Nouveau titre",
                "bio": "Nouvelle bio",
                "skills": ["Django", "DRF"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.title, "Nouveau titre")
        self.assertEqual(self.user.bio, "Nouvelle bio")
        self.assertEqual(self.user.skills, ["Django", "DRF"])

    def test_patch_bio_calls_moderation(self):
        """La modification de la bio relance la modération une fois."""
        self.authenticate()

        response = self.client.patch(
            self.url,
            {"bio": "Bio à vérifier"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.call_llm_mock.assert_called_once()

    def test_patch_hourly_rate_does_not_call_moderation(self):
        """La modification du tarif seul ne relance pas la modération."""
        self.authenticate()

        response = self.client.patch(
            self.url,
            {"hourly_rate": 75},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.call_llm_mock.assert_not_called()

    def test_patch_bio_rejected_status_is_saved(self):
        """Une décision REJETE est persistée après modification de la bio."""
        self.call_llm_mock.return_value = (
            '{"statut": "REJETE", "raison": "Interdit", "confiance": 0.9}'
        )
        self.authenticate()

        response = self.client.patch(
            self.url,
            {"bio": "Bio interdite"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Bio interdite")
        self.assertEqual(self.user.moderation_status, User.ModerationStatus.REJETE)

    def test_patch_ignores_protected_fields(self):
        """PATCH ignore les champs d'identité et de modération protégés."""
        self.authenticate()
        original_role = self.user.role
        original_status = self.user.moderation_status

        response = self.client.patch(
            self.url,
            {"role": User.Role.ADMIN, "moderation_status": User.ModerationStatus.OK},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, original_role)
        self.assertEqual(self.user.moderation_status, original_status)

    def test_patch_rejects_negative_hourly_rate(self):
        """Un tarif horaire négatif est refusé."""
        self.authenticate()

        response = self.client.patch(
            self.url,
            {"hourly_rate": -1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_does_not_expose_sensitive_fields(self):
        """La réponse ne contient aucun champ sensible."""
        self.authenticate()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data)
        self.assertNotIn("is_staff", response.data)
        self.assertNotIn("is_superuser", response.data)

    def test_suspect_user_cannot_access_profile(self):
        """Un utilisateur SUSPECT ne peut pas consulter son profil."""
        self.user.moderation_status = User.ModerationStatus.SUSPECT
        self.user.save(update_fields=("moderation_status",))
        self.authenticate()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_approved_user_can_access_profile(self):
        """Un utilisateur approuvé peut consulter son profil."""
        self.authenticate()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
