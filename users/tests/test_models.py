from django.db import IntegrityError, transaction
from django.test import TestCase

from users.models import User


class UserModelTests(TestCase):
    def test_default_values(self):
        user = User.objects.create_user("arij", "arij@example.com", "motdepasse123")
        self.assertEqual(user.role, User.Role.FREELANCER)
        self.assertEqual(user.moderation_status, User.ModerationStatus.PENDING)
        self.assertEqual(user.skills, [])
        self.assertIsNone(user.moderation_checked_at)

    def test_email_must_be_unique(self):
        User.objects.create_user("u1", "same@example.com", "motdepasse123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("u2", "same@example.com", "motdepasse123")

    def test_str(self):
        user = User.objects.create_user("arij", "a@example.com", "motdepasse123")
        self.assertIn("arij", str(user))

    def test_superuser_is_admin_and_validated(self):
        admin = User.objects.create_superuser("root", "root@example.com", "motdepasse123")
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertEqual(admin.moderation_status, User.ModerationStatus.OK)