import os

from django.core.management.base import BaseCommand

from users.models import User


class Command(BaseCommand):
    """Crée le super admin et des comptes de démonstration."""

    help = "Crée le super admin et des comptes de démonstration"

    def handle(self, *args, **options):
        # Super admin (identifiants modifiables dans le .env)
        su_username = os.getenv("SUPERADMIN_USERNAME", "superadmin")
        su_email = os.getenv("SUPERADMIN_EMAIL", "superadmin@example.com")
        su_password = os.getenv("SUPERADMIN_PASSWORD", "ChangeMe123!")

        if not User.objects.filter(username=su_username).exists():
            User.objects.create_superuser(su_username, su_email, su_password)
            self.stdout.write(self.style.SUCCESS(f"Super admin créé : {su_username}"))
        else:
            self.stdout.write(f"Super admin déjà présent : {su_username}")

        # Comptes de démo : (username, email, mot de passe, rôle, statut)
        demo_users = [
            ("admin", "admin@example.com", "Admin12345!",
             User.Role.ADMIN, User.ModerationStatus.OK),
            ("freelance", "freelance@example.com", "Freelance123!",
             User.Role.FREELANCER, User.ModerationStatus.PENDING),
            ("porteur", "porteur@example.com", "Porteur123!",
             User.Role.PROJECT_OWNER, User.ModerationStatus.PENDING),
        ]

        for username, email, password, role, status in demo_users:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"Déjà présent : {username}")
                continue
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                moderation_status=status,
            )
            self.stdout.write(self.style.SUCCESS(f"Créé : {username} ({role})"))