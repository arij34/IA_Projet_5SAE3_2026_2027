"""Tests de la commande de diagnostic Gemini."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class CheckGeminiCommandTests(SimpleTestCase):
    """Vérifie que le mode mock ne déclenche aucun appel réseau."""

    @override_settings(
        CHATBOT_LLM_PROVIDER="mock",
        GEMINI_API_KEY="",
        GEMINI_MODEL="gemini-test",
    )
    @patch("users.management.commands.check_gemini._call_gemini")
    def test_mock_provider_does_not_call_gemini(self, call_gemini):
        """Le diagnostic mock s'arrête sans appeler Gemini."""
        output = StringIO()

        call_command("check_gemini", stdout=output)

        self.assertIn("Mode mock : aucun appel réseau effectué.", output.getvalue())
        call_gemini.assert_not_called()
