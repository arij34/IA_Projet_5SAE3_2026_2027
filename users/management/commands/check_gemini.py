"""Vérifie la configuration Gemini sans afficher la clé API."""

from django.conf import settings
from django.core.management.base import BaseCommand

from users.ai.llm_client import _call_gemini


class Command(BaseCommand):
    """Contrôle la configuration et la disponibilité du fournisseur Gemini."""

    help = "Vérifie la configuration Gemini du chatbot."

    def handle(self, *args, **options) -> None:
        """Affiche un diagnostic non sensible et teste Gemini si nécessaire."""
        provider = getattr(settings, "CHATBOT_LLM_PROVIDER", "mock")
        api_key = getattr(settings, "GEMINI_API_KEY", "")
        model = getattr(settings, "GEMINI_MODEL", "")

        self.stdout.write(f"Fournisseur chatbot : {provider}")
        self.stdout.write(f"Clé présente : {'oui' if bool(api_key) else 'non'}")
        self.stdout.write(f"Longueur de la clé : {len(api_key)}")
        self.stdout.write(
            f"Commence par AIza : {'oui' if api_key.startswith('AIza') else 'non'}"
        )
        self.stdout.write(f"Modèle : {model}")

        if provider == "mock":
            self.stdout.write("Mode mock : aucun appel réseau effectué.")
            return

        if provider != "gemini":
            self.stdout.write("Erreur : LLMConfigError")
            return

        try:
            _call_gemini(
                "Réponds uniquement par OK.",
                "Vérification de configuration.",
                1,
            )
        except Exception as error:
            self.stdout.write(f"Erreur : {type(error).__name__}")
            return
        self.stdout.write("OK")
