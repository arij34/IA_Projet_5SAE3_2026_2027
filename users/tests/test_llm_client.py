from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from users.ai.exceptions import (
    LLMConfigError,
    LLMQuotaError,
    LLMResponseError,
    LLMTimeoutError,
)
from users.ai.llm_client import call_llm


def fake_response(status=200, body=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body if body is not None else {}
    return response


@override_settings(LLM_PROVIDER="mock")
class MockProviderTests(SimpleTestCase):
    def test_moderation_prompt_returns_status(self):
        self.assertIn("statut", call_llm("Classe avec un statut", "profil"))

    def test_advice_prompt_returns_score(self):
        self.assertIn("score", call_llm("Donne des conseils", "profil"))

    def test_payment_profile_is_suspect(self):
        result = call_llm(
            "Analyse avec un statut",
            "<profil>Paiement hors plateforme obligatoire.</profil>",
        )

        self.assertIn('"statut": "SUSPECT"', result)
        self.assertIn('"confiance": 0.85', result)
        self.assertIn('"probleme": true', result)

    def test_forbidden_profile_is_rejected(self):
        result = call_llm(
            "Analyse avec un statut",
            "<profil>Contenu pour adultes interdit.</profil>",
        )

        self.assertIn('"statut": "REJETE"', result)
        self.assertIn('"confiance": 0.95', result)

    def test_long_neutral_profile_is_confident(self):
        result = call_llm(
            "Analyse avec un statut",
            "<profil>Développeuse Python avec dix ans d'expérience en applications web.</profil>",
        )

        self.assertIn('"statut": "OK"', result)
        self.assertIn('"confiance": 0.88', result)

    def test_short_profile_is_low_confidence(self):
        result = call_llm(
            "Analyse avec un statut",
            "<profil>Python.</profil>",
        )

        self.assertIn('"statut": "OK"', result)
        self.assertIn('"confiance": 0.62', result)
        self.assertIn('"id": "profil_trop_pauvre", "probleme": true', result)

    def test_repeated_word_is_suspect(self):
        result = call_llm(
            "Analyse avec un statut",
            "<profil>" + ("spam " * 9) + "</profil>",
        )

        self.assertIn('"statut": "SUSPECT"', result)


@override_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="cle-test", LLM_MODEL="m", LLM_TIMEOUT_SECONDS=5)
class AnthropicProviderTests(SimpleTestCase):
    @patch("users.ai.llm_client.requests.post")
    def test_success(self, post):
        post.return_value = fake_response(200, {"content": [{"type": "text", "text": '{"ok": true}'}]})
        self.assertEqual(call_llm("sys", "user"), '{"ok": true}')

    @patch("users.ai.llm_client.requests.post")
    def test_quota(self, post):
        post.return_value = fake_response(429)
        with self.assertRaises(LLMQuotaError):
            call_llm("sys", "user")

    @patch("users.ai.llm_client.requests.post")
    def test_timeout_after_retry(self, post):
        post.side_effect = requests.Timeout()
        with self.assertRaises(LLMTimeoutError):
            call_llm("sys", "user")
        self.assertEqual(post.call_count, 2)

    @patch("users.ai.llm_client.requests.post")
    def test_server_error_then_success(self, post):
        post.side_effect = [
            fake_response(500),
            fake_response(200, {"content": [{"type": "text", "text": "ok"}]}),
        ]
        self.assertEqual(call_llm("sys", "user"), "ok")

    @patch("users.ai.llm_client.requests.post")
    def test_empty_content(self, post):
        post.return_value = fake_response(200, {"content": []})
        with self.assertRaises(LLMResponseError):
            call_llm("sys", "user")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_missing_key(self):
        with self.assertRaises(LLMConfigError):
            call_llm("sys", "user")

    @override_settings(LLM_PROVIDER="inconnu")
    def test_unknown_provider(self):
        with self.assertRaises(LLMConfigError):
            call_llm("sys", "user")


@override_settings(
    LLM_PROVIDER="gemini",
    GEMINI_API_KEY="cle-gemini-test",
    GEMINI_MODEL="gemini-test",
    LLM_TIMEOUT_SECONDS=5,
)
class GeminiProviderTests(SimpleTestCase):
    @patch("users.ai.llm_client.requests.post")
    def test_success_and_request_shape(self, post):
        post.return_value = fake_response(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"ok": '}, {"text": "true}"}]
                        }
                    }
                ]
            },
        )

        self.assertEqual(call_llm("sys", "user"), '{"ok": true}')
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-test:generateContent",
        )
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "cle-gemini-test")
        self.assertNotIn("cle-gemini-test", url)
        self.assertNotIn("cle-gemini-test", kwargs["headers"].get("authorization", ""))
        self.assertEqual(
            kwargs["json"],
            {
                "systemInstruction": {"parts": [{"text": "sys"}]},
                "contents": [{"role": "user", "parts": [{"text": "user"}]}],
                "generationConfig": {
                    "maxOutputTokens": 1024,
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
        )

    @patch("users.ai.llm_client.requests.post")
    def test_quota(self, post):
        post.return_value = fake_response(429)
        with self.assertRaises(LLMQuotaError):
            call_llm("sys", "user")

    @patch("users.ai.llm_client.requests.post")
    def test_forbidden(self, post):
        post.return_value = fake_response(403)
        with self.assertRaises(LLMConfigError):
            call_llm("sys", "user")

    @patch("users.ai.llm_client.requests.post")
    def test_timeout_after_retry(self, post):
        post.side_effect = requests.Timeout()
        with self.assertRaises(LLMTimeoutError) as raised:
            call_llm("sys", "user")
        self.assertEqual(post.call_count, 2)
        self.assertNotIn("cle-gemini-test", str(raised.exception))

    @patch("users.ai.llm_client.requests.post")
    def test_server_error_then_success(self, post):
        post.side_effect = [
            fake_response(500),
            fake_response(
                200,
                {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
            ),
        ]
        self.assertEqual(call_llm("sys", "user"), "ok")
        self.assertEqual(post.call_count, 2)

    @patch("users.ai.llm_client.requests.post")
    def test_missing_candidates(self, post):
        post.return_value = fake_response(200, {"candidates": []})
        with self.assertRaises(LLMResponseError):
            call_llm("sys", "user")

    @patch("users.ai.llm_client.requests.post")
    def test_blocked_response_without_text(self, post):
        post.return_value = fake_response(
            200,
            {"candidates": [{"finishReason": "SAFETY"}]},
        )
        with self.assertRaises(LLMResponseError):
            call_llm("sys", "user")

    @override_settings(GEMINI_API_KEY="")
    def test_missing_key(self):
        with self.assertRaises(LLMConfigError) as raised:
            call_llm("sys", "user")
        self.assertNotIn("cle-gemini-test", str(raised.exception))
