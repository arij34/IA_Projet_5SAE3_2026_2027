"""Tests for the Mistral project test-case generator and its API endpoint."""

import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from projects.ai.test_cases import (
    TestCaseProviderConfigurationError,
    TestCaseProviderRateLimitError,
    TestCaseProviderTimeoutError,
    TestCaseResponseValidationError,
    generate_test_cases,
    parse_test_cases,
)
from projects.models import Project


def valid_payload():
    case = {
        "title": "Création d'un compte valide",
        "requirement": "Un visiteur peut s'inscrire avec un courriel valide.",
        "priority": "high",
        "category": "functional",
        "preconditions": ["Le visiteur est déconnecté."],
        "steps": ["Ouvrir le formulaire.", "Saisir des informations valides.", "Valider le formulaire."],
        "expected_result": "Le compte est créé et une confirmation s'affiche.",
    }
    return {"test_cases": [dict(case, title=f"{case['title']} {index}") for index in range(3)]}


@override_settings(MISTRAL_TEST_CASE_THROTTLE_RATE="100/hour")
class ProjectTestCaseApiTests(TestCase):
    url_template = "/api/projects/{}/test-cases/"

    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="qa-owner", email="qa-owner@example.com", password="pass12345", role="PROJECT_OWNER"
        )
        self.other_owner = user_model.objects.create_user(
            username="qa-other", email="qa-other@example.com", password="pass12345", role="PROJECT_OWNER"
        )
        self.project = Project.objects.create(
            owner=self.owner,
            name="Application de réservation",
            description="Un utilisateur peut consulter des créneaux et réserver une séance.",
            deadline=date.today() + timedelta(days=45),
            estimated_amount=Decimal("5000.00"),
        )
        cache.clear()
        self.client.force_authenticate(user=self.owner)

    def url(self):
        return self.url_template.format(self.project.pk)

    @patch("projects.ai.test_cases.requests.post")
    @override_settings(MISTRAL_API_KEY="test-key", MISTRAL_TEST_CASE_MODEL="ministral-14b-2512")
    def test_provider_call_uses_server_key_model_and_sanitized_project_text(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(valid_payload(), ensure_ascii=False)}}]
        }
        post.return_value = response
        self.project.description = "Écrire à qa@example.com pour les réservations."
        self.project.save(update_fields=("description",))

        result = generate_test_cases(self.project.name, self.project.description)

        self.assertEqual(len(result), 3)
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "ministral-14b-2512")
        self.assertIn("[EMAIL]", payload["messages"][1]["content"])
        self.assertNotIn("qa@example.com", payload["messages"][1]["content"])

    @override_settings(MISTRAL_API_KEY="")
    def test_missing_credentials_fail_without_provider_request(self):
        with patch("projects.ai.test_cases.requests.post") as post:
            with self.assertRaises(TestCaseProviderConfigurationError):
                generate_test_cases("Projet", "Description")
        post.assert_not_called()

    @override_settings(MISTRAL_API_KEY="test-key")
    def test_timeout_and_provider_rate_limit_are_distinguished(self):
        with patch("projects.ai.test_cases.requests.post", side_effect=requests.Timeout):
            with self.assertRaises(TestCaseProviderTimeoutError):
                generate_test_cases("Projet", "Description")
        rate_limit = Mock(status_code=429)
        with patch("projects.ai.test_cases.requests.post", return_value=rate_limit):
            with self.assertRaises(TestCaseProviderRateLimitError):
                generate_test_cases("Projet", "Description")

    def test_malformed_or_out_of_contract_model_outputs_are_rejected(self):
        for raw in ("not json", "[]", json.dumps({"test_cases": []})):
            with self.subTest(raw=raw):
                with self.assertRaises(TestCaseResponseValidationError):
                    parse_test_cases(raw)
        malformed = valid_payload()
        malformed["test_cases"][0]["priority"] = "urgent"
        with self.assertRaises(TestCaseResponseValidationError):
            parse_test_cases(json.dumps(malformed))

    @patch("projects.views.generate_test_cases", return_value=valid_payload()["test_cases"])
    def test_owner_receives_validated_cases_and_model_metadata(self, generate):
        response = self.client.post(self.url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "mistral")
        self.assertEqual(response.data["test_cases"][0]["priority"], "high")
        generate.assert_called_once_with(self.project.name, self.project.description)

    @patch("projects.views.generate_test_cases", side_effect=TestCaseProviderConfigurationError("hidden"))
    def test_missing_provider_configuration_returns_safe_service_error(self, _generate):
        response = self.client.post(self.url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "provider_not_configured")
        self.assertNotIn("hidden", str(response.data))

    def test_other_owner_cannot_use_project_endpoint(self):
        self.client.force_authenticate(user=self.other_owner)
        response = self.client.post(self.url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_freelancer_cannot_use_project_endpoint(self):
        freelancer = get_user_model().objects.create_user(
            username="qa-freelancer", email="qa-freelancer@example.com", password="pass12345", role="FREELANCER"
        )
        self.client.force_authenticate(user=freelancer)
        response = self.client.post(self.url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_authentication_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
