from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


User = get_user_model()


class AdminSiteTests(TestCase):
    """Teste la synchronisation du statut de modération depuis l'admin."""

    def setUp(self):
        """Authentifie un superutilisateur dans le client Django."""
        self.admin = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="MotDePasseFort!123",
        )
        self.client.force_login(self.admin)

    def add_payload(self, role):
        """Construit les champs du formulaire d'ajout utilisateur."""
        return {
            "username": f"user-{role.lower()}",
            "password1": "MotDePasseFort!123",
            "password2": "MotDePasseFort!123",
            "email": f"{role.lower()}@example.com",
            "role": role,
        }

    def test_admin_role_created_from_admin_is_approved_without_staff_access(self):
        """Un ADMIN créé dans Django est approuvé sans devenir staff."""
        response = self.client.post(
            reverse("admin:users_user_add"),
            self.add_payload(User.Role.ADMIN),
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="user-admin")
        self.assertEqual(user.moderation_status, User.ModerationStatus.OK)
        self.assertFalse(user.is_staff)

    def test_admin_role_can_login_through_api(self):
        """Un ADMIN créé par l'admin Django peut se connecter à l'API."""
        self.client.post(
            reverse("admin:users_user_add"),
            self.add_payload(User.Role.ADMIN),
        )
        api_client = APIClient()

        response = api_client.post(
            "/api/auth/login/",
            {
                "username": "user-admin",
                "password": "MotDePasseFort!123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["token"])

    def test_promoting_existing_user_to_admin_approves_it(self):
        """Le passage d'un utilisateur existant à ADMIN l'approuve."""
        user = User.objects.create_user(
            username="promotion",
            email="promotion@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
        )
        user.role = User.Role.ADMIN
        user.moderation_status = User.ModerationStatus.PENDING
        user.moderation_checked_at = None
        user.save()

        from django.contrib import admin

        admin.site._registry[User].save_model(
            self.admin,
            user,
            form=None,
            change=True,
        )
        user.refresh_from_db()

        self.assertEqual(user.moderation_status, User.ModerationStatus.OK)
        self.assertIsNotNone(user.moderation_checked_at)

    def test_freelancer_created_from_admin_remains_pending(self):
        """Un freelance créé depuis l'admin reste en attente."""
        response = self.client.post(
            reverse("admin:users_user_add"),
            self.add_payload(User.Role.FREELANCER),
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="user-freelancer")
        self.assertEqual(user.moderation_status, User.ModerationStatus.PENDING)
