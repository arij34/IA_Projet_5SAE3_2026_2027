"""Configuration de l'application matching."""

from django.apps import AppConfig


class MatchingConfig(AppConfig):
    """Déclare l'application de mise en relation projet / freelance."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "matching"
    verbose_name = "Matching"
