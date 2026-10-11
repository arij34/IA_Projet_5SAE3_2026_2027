from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class LoginApiTests(APITestCase):
    """Teste l'endpoint public de connexion."""

    url = "/api/auth/login/"

    def setUp(self):
        """Prépare un compte actif réutilisable par les tests."""
        self.user = User.objects.create_user(
            username="connecte",
            email="connecte@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )

    def payload(self, password="MotDePasseFort!123"):
        """Construit les identifiants de connexion."""
        return {"username": self.user.username, "password": password}

    def test_valid_login_returns_token_and_public_user(self):
        """Une connexion valide retourne un jeton et les données publiques."""
        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["token"])
        self.assertEqual(response.data["user"]["username"], self.user.username)
        self.assertNotIn("password", response.data["user"])

    def test_wrong_password_returns_generic_error(self):
        """Un mauvais mot de passe retourne une erreur générique."""
        response = self.client.post(
            self.url,
            self.payload(password="MauvaisMotDePasse!123"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["non_field_errors"], ["Identifiants invalides."])

    def test_suspect_user_cannot_login_without_token(self):
        """Un profil SUSPECT reçoit un refus métier sans jeton."""
        self.user.moderation_status = User.ModerationStatus.SUSPECT
        self.user.save(update_fields=("moderation_status",))

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("token", response.data)
        self.assertEqual(
            response.data["moderation_status"],
            User.ModerationStatus.SUSPECT,
        )
        self.assertEqual(
            response.data["detail"],
            "Votre profil est en cours de vérification par un administrateur.",
        )

    def test_rejected_user_cannot_login(self):
        """Un profil REJETE reçoit un refus métier."""
        self.user.moderation_status = User.ModerationStatus.REJETE
        self.user.save(update_fields=("moderation_status",))

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("token", response.data)
        self.assertEqual(response.data["moderation_status"], User.ModerationStatus.REJETE)
        self.assertEqual(response.data["detail"], "Votre profil a été refusé.")

    def test_pending_user_cannot_login(self):
        """Un profil PENDING reçoit un refus métier."""
        self.user.moderation_status = User.ModerationStatus.PENDING
        self.user.save(update_fields=("moderation_status",))

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("token", response.data)
        self.assertEqual(response.data["moderation_status"], User.ModerationStatus.PENDING)

    def test_unknown_user_returns_same_generic_error(self):
        """Un utilisateur inconnu retourne le même message générique."""
        response = self.client.post(
            self.url,
            {"username": "inconnu", "password": "MauvaisMotDePasse!123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["non_field_errors"], ["Identifiants invalides."])

    def test_disabled_account_cannot_login(self):
        """Un compte désactivé ne peut pas obtenir de jeton."""
        self.user.is_active = False
        self.user.save(update_fields=("is_active",))

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["non_field_errors"], ["Identifiants invalides."])
