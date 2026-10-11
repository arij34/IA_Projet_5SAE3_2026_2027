from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import ModerationLog


User = get_user_model()


class AdminModerationApiTests(APITestCase):
    """Teste l'API de modération réservée aux administrateurs."""

    base_url = "/api/admin/moderation/"

    def setUp(self):
        """Prépare un administrateur et des profils dans chaque statut."""
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="MotDePasseFort!123",
        )
        self.suspect = self.create_user("suspect", User.ModerationStatus.SUSPECT)
        self.pending = self.create_user("pending", User.ModerationStatus.PENDING)
        self.rejected = self.create_user("rejected", User.ModerationStatus.REJETE)
        self.approved = self.create_user("approved", User.ModerationStatus.OK)
        self.other_admin = User.objects.create_superuser(
            username="other-admin",
            email="other-admin@example.com",
            password="MotDePasseFort!123",
        )

    def create_user(self, username, moderation_status):
        """Crée un profil de test avec le statut fourni."""
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
            moderation_status=moderation_status,
            title=f"Titre {username}",
            bio=f"Bio {username}",
            skills=["Django"],
        )

    def authenticate_as(self, user):
        """Authentifie le client comme l'utilisateur fourni."""
        self.client.force_authenticate(user=user)

    def test_unauthenticated_user_is_rejected(self):
        """Un appel sans jeton reçoit 401."""
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_users_are_rejected(self):
        """Les utilisateurs approuvés non administrateurs reçoivent 403."""
        for user in (self.approved, self.create_user("owner", User.ModerationStatus.OK)):
            with self.subTest(role=user.role):
                self.authenticate_as(user)
                response = self.client.get(self.base_url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_excludes_approved_and_admin_users(self):
        """La liste contient les profils modérables, mais aucun approuvé ni admin."""
        self.authenticate_as(self.admin)

        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item["username"] for item in response.data}
        self.assertEqual(usernames, {"suspect", "pending", "rejected"})

    def test_list_filter_and_invalid_filter(self):
        """Le filtre REJETE fonctionne et les statuts inconnus sont refusés."""
        self.authenticate_as(self.admin)

        filtered = self.client.get(f"{self.base_url}?status=REJETE")
        invalid = self.client.get(f"{self.base_url}?status=abc")

        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["username"] for item in filtered.data],
            ["rejected"],
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detail_contains_history_without_password(self):
        """Le détail expose l'historique sans aucune donnée de mot de passe."""
        ModerationLog.objects.create(
            user=self.suspect,
            decision=User.ModerationStatus.SUSPECT,
            reason="Motif de test",
            confidence=0.4,
            error="",
        )
        self.authenticate_as(self.admin)

        response = self.client.get(f"{self.base_url}{self.suspect.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data)
        self.assertEqual(response.data["moderation_logs"][0]["reason"], "Motif de test")

    def test_approve_suspect_updates_status_and_creates_log(self):
        """L'approbation d'un profil SUSPECT est persistée et journalisée."""
        self.authenticate_as(self.admin)

        response = self.client.post(f"{self.base_url}{self.suspect.id}/approve/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.suspect.refresh_from_db()
        self.assertEqual(self.suspect.moderation_status, User.ModerationStatus.OK)
        log = self.suspect.moderation_logs.latest("created_at")
        self.assertEqual(log.decision, User.ModerationStatus.OK)
        self.assertEqual(log.reason, "Validé manuellement par admin")
        self.assertIsNone(log.confidence)

    def test_approve_pending_updates_status(self):
        """L'approbation d'un profil PENDING est acceptée."""
        self.authenticate_as(self.admin)

        response = self.client.post(f"{self.base_url}{self.pending.id}/approve/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.moderation_status, User.ModerationStatus.OK)

    def test_approve_rejected_returns_conflict(self):
        """Un profil REJETE ne peut pas être approuvé."""
        self.authenticate_as(self.admin)

        response = self.client.post(f"{self.base_url}{self.rejected.id}/approve/")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.rejected.refresh_from_db()
        self.assertEqual(
            self.rejected.moderation_status,
            User.ModerationStatus.REJETE,
        )

    def test_delete_rejected_user(self):
        """Un profil REJETE peut être supprimé."""
        self.authenticate_as(self.admin)

        response = self.client.delete(f"{self.base_url}{self.rejected.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.rejected.pk).exists())

    def test_other_admin_is_not_visible_or_mutable(self):
        """Un administrateur ne peut pas agir sur un autre administrateur."""
        self.authenticate_as(self.admin)

        detail = self.client.get(f"{self.base_url}{self.other_admin.id}/")
        approve = self.client.post(
            f"{self.base_url}{self.other_admin.id}/approve/"
        )
        delete = self.client.delete(f"{self.base_url}{self.other_admin.id}/")

        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(approve.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_approved_user_is_not_deletable_via_moderation_api(self):
        """Un utilisateur approuvé est hors du périmètre de suppression."""
        self.authenticate_as(self.admin)

        response = self.client.delete(f"{self.base_url}{self.approved.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(User.objects.filter(pk=self.approved.pk).exists())
