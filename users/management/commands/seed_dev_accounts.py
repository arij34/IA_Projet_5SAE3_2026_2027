"""Crée des comptes de développement local (ne jamais utiliser en production).

Ces identifiants sont volontairement écrits en clair : ils ne servent qu'au
développement sur une base SQLite locale et n'ont aucune valeur ailleurs.

Usage :
    python manage.py seed_dev_accounts
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import User


DEV_PASSWORD = "Freelancy2026!"

DEV_ACCOUNTS = [
    {
        "username": "admin",
        "email": "admin@freelancy.local",
        "role": User.Role.ADMIN,
        "is_staff": True,
        "is_superuser": True,
        "moderation_status": User.ModerationStatus.OK,
        "title": "",
        "bio": "",
        "skills": [],
        "hourly_rate": None,
    },
    {
        "username": "freelance",
        "email": "freelance@freelancy.local",
        "role": User.Role.FREELANCER,
        "is_staff": False,
        "is_superuser": False,
        "moderation_status": User.ModerationStatus.OK,
        "title": "Développeuse back-end Python",
        "bio": "Six ans d'expérience sur des API Django et des pipelines de données.",
        "skills": ["Python", "Django", "PostgreSQL", "Docker", "REST"],
        "hourly_rate": 55,
    },
    {
        "username": "porteur",
        "email": "porteur@freelancy.local",
        "role": User.Role.PROJECT_OWNER,
        "is_staff": False,
        "is_superuser": False,
        "moderation_status": User.ModerationStatus.OK,
        "title": "",
        "bio": "",
        "skills": [],
        "hourly_rate": None,
    },
]


class Command(BaseCommand):
    """Crée ou met à jour les comptes de démonstration locaux."""

    help = "Crée les comptes de développement (admin, freelance, porteur)."

    @transaction.atomic
    def handle(self, *args, **options):
        """Crée chaque compte s'il n'existe pas, puis réinitialise son mot de passe."""
        for data in DEV_ACCOUNTS:
            defaults = {k: v for k, v in data.items() if k != "username"}
            user, created = User.objects.get_or_create(
                username=data["username"], defaults=defaults
            )
            if not created:
                for field, value in defaults.items():
                    setattr(user, field, value)
            user.set_password(DEV_PASSWORD)
            user.save()
            state = "créé" if created else "mis à jour"
            self.stdout.write(f"{user.username} ({user.get_role_display()}) : {state}")
        self.stdout.write(
            self.style.SUCCESS("Comptes de développement prêts.")
        )
