"""Tests unitaires du client LLM de projects."""

from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from projects.ai.client import (
    ANTHROPIC_API_VERSION,
    ANTHROPIC_MESSAGES_URL,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    call_llm,
)
from projects.ai.exceptions import (
    LLMAuthError,
    LLMConfigError,
    LLMQuotaError,
    LLMResponseError,
    LLMServiceError,
    LLMTimeoutError,
)


def anthropic_response(text: str = "réponse valide") -> Mock:
    """Construit une réponse HTTP Anthropic minimale et valide."""
    response = Mock(status_code=200)
    response.json.return_value = {
        "content": [{"type": "text", "text": text}],
    }
    return response


class LlmClientTests(SimpleTestCase):
    """Vérifie les appels, reprises et erreurs du client Anthropic."""

    settings = {
        "PROJECT_LLM_PROVIDER": "anthropic",
        "PROJECT_LLM_API_KEY": "secret-test-key",
        "PROJECT_LLM_MODEL": "configured-model",
    }

    @override_settings(**settings)
    @patch("projects.ai.client.requests.post")
    def test_success(self, post: Mock) -> None:
        """Un contenu textuel valide est retourné."""
        post.return_value = anthropic_response()

        result = call_llm("system", "project data")

        self.assertEqual(result, "réponse valide")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], ANTHROPIC_MESSAGES_URL)
        self.assertEqual(post.call_args.kwargs["headers"]["x-api-key"], "secret-test-key")
        self.assertEqual(
            post.call_args.kwargs["headers"]["anthropic-version"],
            ANTHROPIC_API_VERSION,
        )
        self.assertEqual(
            post.call_args.kwargs["timeout"],
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 4096)
        self.assertEqual(post.call_args.kwargs["json"]["temperature"], 0.2)

    @override_settings(
        **settings,
        PROJECT_LLM_MAX_TOKENS=6000,
        PROJECT_LLM_TEMPERATURE=0.1,
        PROJECT_LLM_TIMEOUT=60,
    )
    @patch("projects.ai.client.requests.post")
    def test_response_length_settings_are_transmitted(self, post: Mock) -> None:
        """Les réglages de longueur, température et timeout sont transmis."""
        post.return_value = anthropic_response()

        call_llm("system", "project data")

        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 6000)
        self.assertEqual(post.call_args.kwargs["json"]["temperature"], 0.1)
        self.assertEqual(post.call_args.kwargs["timeout"], 60)

    @override_settings(**settings)
    @patch("projects.ai.client.requests.post")
    def test_timeout_is_retried_once(self, post: Mock) -> None:
        """Un timeout est retenté une fois puis converti en erreur dédiée."""
        post.side_effect = [requests.Timeout(), requests.Timeout()]

        with self.assertRaises(LLMTimeoutError):
            call_llm("system", "project data")

        self.assertEqual(post.call_count, 2)

    @override_settings(**settings)
    @patch("projects.ai.client.requests.post")
    def test_quota_error(self, post: Mock) -> None:
        """Le statut 429 devient une erreur de quota sans réessai."""
        post.return_value = Mock(status_code=429)

        with self.assertRaises(LLMQuotaError):
            call_llm("system", "project data")

        post.assert_called_once()

    @override_settings(**settings)
    @patch("projects.ai.client.requests.post")
    def test_auth_error_for_401_and_403(self, post: Mock) -> None:
        """Les statuts d'authentification deviennent une erreur dédiée."""
        for status_code in (401, 403):
            post.reset_mock()
            post.return_value = Mock(status_code=status_code)
            with self.assertRaises(LLMAuthError):
                call_llm("system", "project data")

    @override_settings(**settings)
    @patch("projects.ai.client.requests.post")
    def test_service_error_500_is_retried_once(self, post: Mock) -> None:
        """Une erreur 5xx est retentée une fois puis convertie."""
        post.side_effect = [Mock(status_code=500), Mock(status_code=500)]

        with self.assertRaises(LLMServiceError):
            call_llm("system", "project data")

        self.assertEqual(post.call_count, 2)

    @override_settings(
        PROJECT_LLM_PROVIDER="anthropic",
        PROJECT_LLM_API_KEY="",
        PROJECT_LLM_MODEL="configured-model",
    )
    @patch("projects.ai.client.requests.post")
    def test_missing_key_does_not_call_network(self, post: Mock) -> None:
        """Une clé absente est rejetée avant tout appel réseau."""
        with self.assertRaises(LLMConfigError):
            call_llm("system", "project data")
        post.assert_not_called()

    @override_settings(
        PROJECT_LLM_PROVIDER="mock",
        PROJECT_LLM_API_KEY="secret-test-key",
        PROJECT_LLM_MODEL="configured-model",
    )
    @patch("projects.ai.client.requests.post")
    def test_mock_provider_returns_simulated_analysis_without_network(
        self,
        post: Mock,
    ) -> None:
        """Le mode mock utilise le simulateur sans appel réseau."""
        result = call_llm(
            "system",
            (
                "<projet>\n"
                "nom : Site mobile\n"
                "description : Projet de site mobile détaillé.\n"
                "montant estimé : 10000.00\n"
                "</projet>"
            ),
        )
        self.assertIn('"coherence_budget"', result)
        post.assert_not_called()

    @override_settings(
        PROJECT_LLM_PROVIDER="gemini",
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_MODEL="gemini-test-model",
    )
    @patch("users.ai.llm_client._call_gemini")
    def test_gemini_provider_is_used_for_project_analysis(
        self,
        call_gemini: Mock,
    ) -> None:
        """L'analyse de projet utilise le client Gemini partagé."""
        call_gemini.return_value = '{"analysis": "valide"}'

        result = call_llm("system", "project data")

        self.assertEqual(result, '{"analysis": "valide"}')
        call_gemini.assert_called_once_with(
            "system",
            "project data",
            4096,
        )

    @override_settings(
        PROJECT_LLM_PROVIDER="gemini",
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_MODEL="gemini-test-model",
    )
    @patch("users.ai.llm_client._call_gemini")
    def test_gemini_error_is_translated_for_project_analysis(
        self,
        call_gemini: Mock,
    ) -> None:
        """Une erreur Gemini devient une exception projects contrôlée."""
        from users.ai.exceptions import LLMQuotaError as UsersLLMQuotaError

        call_gemini.side_effect = UsersLLMQuotaError("détail fournisseur")

        with self.assertRaises(LLMQuotaError) as raised:
            call_llm("system", "project data")

        self.assertEqual(str(raised.exception), "Le quota Gemini est dépassé.")

    @override_settings(**settings)
    @patch("projects.ai.client.requests.post")
    def test_null_content_raises_response_error(self, post: Mock) -> None:
        """Un champ content nul est refusé proprement."""
        response = Mock(status_code=200)
        response.json.return_value = {"content": None}
        post.return_value = response

        with self.assertRaises(LLMResponseError):
            call_llm("system", "project data")

    @override_settings(**settings)
    @patch("projects.ai.client.requests.post")
    def test_errors_do_not_expose_key_or_payload_in_messages_or_logs(
        self,
        post: Mock,
    ) -> None:
        """Les erreurs et logs ne contiennent ni clé ni données de requête."""
        post.side_effect = [requests.Timeout(), requests.Timeout()]

        with self.assertLogs("projects.ai.client", level="WARNING") as logs:
            with self.assertRaises(LLMTimeoutError) as raised:
                call_llm("system", "private project text")

        combined = str(raised.exception) + " ".join(logs.output)
        self.assertNotIn("secret-test-key", combined)
        self.assertNotIn("private project text", combined)
        self.assertNotIn(ANTHROPIC_MESSAGES_URL, combined)
