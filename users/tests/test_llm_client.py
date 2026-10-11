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
