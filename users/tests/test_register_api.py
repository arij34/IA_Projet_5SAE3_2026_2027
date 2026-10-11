from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from users.ai.exceptions import LLMTimeoutError


User = get_user_model()


class RegisterApiTests(APITestCase):
    """Teste l'endpoint public d'inscription."""

    url = "/api/auth/register/"

    def setUp(self):
        """Configure une réponse LLM valide par défaut pour les tests."""
        self.call_llm = patch("users.services.moderation.call_llm")
        self.call_llm_mock = self.call_llm.start()
        self.call_llm_mock.return_value = (
            '{"statut": "OK", "raison": "Profil cohérent", "confiance": 0.9}'
        )
        self.addCleanup(self.call_llm.stop)

    def valid_payload(self):
        """Retourne les données valides communes aux tests."""
        return {
            "username": "nouveau",
            "email": "nouveau@example.com",
            "password": "MotDePasseFort!123",
            "role": User.Role.FREELANCER,
            "title": "Développeur Django",
            "bio": "Je crée des applications web.",
            "skills": ["Django", "Python"],
        }

    def test_valid_registration_returns_public_data(self):
        """Une inscription valide retourne 201 sans exposer le mot de passe."""
        response = self.client.post(self.url, self.valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)
        self.assertEqual(response.data["moderation_status"], User.ModerationStatus.OK)
        user = User.objects.get(username="nouveau")
        self.assertTrue(user.check_password("MotDePasseFort!123"))

    def test_admin_role_is_rejected(self):
        """Le rôle ADMIN ne peut pas être choisi à l'inscription."""
        payload = self.valid_payload()
        payload["role"] = User.Role.ADMIN

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_protected_moderation_status_is_ignored(self):
        """Un statut de modération fourni par le client est ignoré."""
        payload = self.valid_payload()
        payload["moderation_status"] = User.ModerationStatus.OK

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["moderation_status"], User.ModerationStatus.OK)
        self.assertEqual(
            User.objects.get(username="nouveau").moderation_status,
            User.ModerationStatus.OK,
        )

    def test_duplicate_email_is_rejected(self):
        """Une adresse e-mail déjà utilisée est refusée."""
        payload = self.valid_payload()
        User.objects.create_user(
            username="existant",
            email=payload["email"],
            password="MotDePasseFort!123",
        )

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_moderation_returns_suspect(self):
        """Une réponse SUSPECT du LLM est reflétée dans la réponse."""
        self.call_llm_mock.return_value = (
            '{"statut": "SUSPECT", "raison": "Doute", "confiance": 0.9}'
        )

        response = self.client.post(self.url, self.valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["moderation_status"], User.ModerationStatus.SUSPECT)

    def test_registration_moderation_returns_rejected(self):
        """Une réponse REJETE du LLM est reflétée dans la réponse."""
        self.call_llm_mock.return_value = (
            '{"statut": "REJETE", "raison": "Interdit", "confiance": 0.9}'
        )

        response = self.client.post(self.url, self.valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["moderation_status"], User.ModerationStatus.REJETE)

    def test_registration_llm_timeout_returns_suspect(self):
        """Un timeout LLM conserve une réponse d'inscription normale."""
        self.call_llm_mock.side_effect = LLMTimeoutError()

        response = self.client.post(self.url, self.valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["moderation_status"], User.ModerationStatus.SUSPECT)

    def test_weak_password_is_rejected(self):
        """Un mot de passe trop faible est refusé par Django."""
        payload = self.valid_payload()
        payload["password"] = "123"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
