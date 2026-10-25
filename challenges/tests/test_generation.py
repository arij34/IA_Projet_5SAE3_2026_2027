"""Tests de la génération de quiz; aucun appel réseau réel n'est effectué."""

import json
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from challenges.models import AnswerChoice, ChallengeCategory, Quiz
from challenges.services import generation

User = get_user_model()
URL = "/api/challenges/quizzes/generate/"


def valid_payload(count=20):
    return {
        "title": "Python : itérables",
        "questions": [
            {
                "text": f"Question {i} ?",
                "choices": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"],
                "correct_index": i % 4,
                "explanation": f"Explication {i}.",
            }
            for i in range(count)
        ],
    }


def openai_response(content, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return response


class QuizGenerationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="gen-user",
            email="gen-user@example.com",
            password="pass-12345-xyz",
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        self.category = ChallengeCategory.objects.get(slug="python")
        self.body = {"category": "python", "difficulty": "BEGINNER"}

    def auth(self, user=None):
        token, _ = Token.objects.get_or_create(user=user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_anonymous_pending_and_owner_are_denied(self):
        self.assertEqual(self.client.post(URL, self.body).status_code, 401)
        pending = User.objects.create_user(
            username="gen-pending", email="p@example.com",
            password="pass-12345-xyz", role=User.Role.FREELANCER,
        )
        owner = User.objects.create_user(
            username="gen-owner", email="o@example.com",
            password="pass-12345-xyz", role=User.Role.PROJECT_OWNER,
            moderation_status=User.ModerationStatus.OK,
        )
        admin = User.objects.create_user(
            username="gen-admin", email="a@example.com",
            password="pass-12345-xyz", role=User.Role.ADMIN,
            moderation_status=User.ModerationStatus.OK,
        )
        for denied in (pending, owner, admin):
            self.auth(denied)
            self.assertEqual(self.client.post(URL, self.body).status_code, 403)
        self.assertEqual(Quiz.objects.filter(source="AI_GENERATED").count(), 0)

    @override_settings(CHALLENGE_LLM_PROVIDER="mock")
    def test_mock_generation_creates_unpublished_quiz_without_answer_key(self):
        self.auth()
        response = self.client.post(URL, self.body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["question_count"], 20)
        self.assertNotIn("is_correct", json.dumps(response.data))
        self.assertNotIn("explanation", json.dumps(response.data))
        quiz = Quiz.objects.get(pk=response.data["id"])
        self.assertEqual(quiz.status, Quiz.Status.DRAFT)
        self.assertEqual(quiz.category, self.category)
        self.assertEqual(quiz.difficulty, "BEGINNER")
        self.assertEqual(quiz.source, Quiz.Source.AI_GENERATED)
        self.assertEqual(quiz.generated_by, self.user)
        self.assertEqual(quiz.prompt_version, generation.PROMPT_VERSION)
        for question in quiz.questions.all():
            self.assertEqual(question.choices.filter(is_correct=True).count(), 1)

    @override_settings(CHALLENGE_LLM_PROVIDER="mock")
    def test_generated_quiz_can_be_listed_attempted_scored_and_completed(self):
        self.auth()
        generated = self.client.post(URL, self.body, format="json")
        self.assertEqual(generated.status_code, status.HTTP_201_CREATED)
        quiz_id = generated.data["id"]
        # Mock output is a draft; publish it explicitly to exercise the attempt flow.
        Quiz.objects.filter(pk=quiz_id).update(status=Quiz.Status.PUBLISHED)

        listed = self.client.get(
            "/api/challenges/quizzes/?category=python&difficulty=BEGINNER"
        )
        self.assertIn(quiz_id, [item["id"] for item in listed.data])
        detail = self.client.get(f"/api/challenges/quizzes/{quiz_id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data["questions"]), 20)
        self.assertNotIn("explanation", json.dumps(detail.data))

        started = self.client.post(
            "/api/challenges/attempts/",
            {"quiz_id": quiz_id},
            format="json",
        )
        self.assertEqual(started.status_code, status.HTTP_201_CREATED)
        attempt_id = started.data["id"]
        quiz = Quiz.objects.get(pk=quiz_id)
        for question in quiz.questions.all():
            correct_choice = question.choices.get(is_correct=True)
            answer = self.client.post(
                f"/api/challenges/attempts/{attempt_id}/answers/",
                {"question_id": question.pk, "choice_id": correct_choice.pk},
                format="json",
            )
            self.assertEqual(answer.status_code, status.HTTP_201_CREATED)
            self.assertNotIn("is_correct", answer.data)

        completed = self.client.post(
            f"/api/challenges/attempts/{attempt_id}/complete/"
        )
        results = self.client.get(
            f"/api/challenges/attempts/{attempt_id}/results/"
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual(completed.data["correct_answers"], 20)
        self.assertEqual(completed.data["score_percent"], 100)
        self.assertEqual(results.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results.data["answers"]), 20)
        self.assertTrue(all(item["is_correct"] for item in results.data["answers"]))
        self.assertTrue(all(item["explanation"] for item in results.data["answers"]))

    def test_invalid_input_is_rejected(self):
        self.auth()
        for body in (
            {"category": "nope", "difficulty": "BEGINNER"},
            {"category": "python", "difficulty": "EXPERT"},
            {"difficulty": "BEGINNER"},
        ):
            self.assertEqual(self.client.post(URL, body, format="json").status_code, 400)

    @override_settings(CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4o-mini")
    @patch("challenges.services.generation.requests.post")
    def test_openai_success_uses_mocked_http_and_records_provenance(self, post):
        post.return_value = openai_response(json.dumps(valid_payload()))
        self.auth()
        response = self.client.post(URL, self.body, format="json")
        self.assertEqual(response.status_code, 201)
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], "gpt-4o-mini")
        self.assertIn("Python", kwargs["json"]["messages"][1]["content"])
        quiz = Quiz.objects.get(pk=response.data["id"])
        self.assertEqual((quiz.llm_provider, quiz.llm_model), ("openai", "gpt-4o-mini"))
        self.assertNotIn("test-key", json.dumps(response.data))

    @override_settings(CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="")
    @patch("challenges.services.generation.requests.post")
    def test_missing_key_returns_503_without_network_call(self, post):
        self.auth()
        self.assertEqual(self.client.post(URL, self.body, format="json").status_code, 503)
        post.assert_not_called()

    @override_settings(CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="k")
    @patch("challenges.services.generation.requests.post")
    def test_upstream_failures_map_to_errors_and_persist_nothing(self, post):
        self.auth()
        before = Quiz.objects.count()
        cases = [
            (requests.Timeout(), 504),
            (requests.ConnectionError(), 502),
            (openai_response("", 429), 503),
            (openai_response("", 500), 502),
            (openai_response("not json"), 502),
        ]
        for effect, expected in cases:
            cache.clear()
            post.side_effect = effect if isinstance(effect, Exception) else None
            if not isinstance(effect, Exception):
                post.return_value = effect
            response = self.client.post(URL, self.body, format="json")
            self.assertEqual(response.status_code, expected)
        self.assertEqual(Quiz.objects.count(), before)

    # The provider is pinned to the mock: .env may select the real provider.
    @override_settings(CHALLENGE_GENERATION_THROTTLE_RATE="1/hour", CHALLENGE_LLM_PROVIDER="mock")
    def test_generation_is_throttled_per_user(self):
        self.auth()
        self.assertEqual(self.client.post(URL, self.body, format="json").status_code, 201)
        self.assertEqual(self.client.post(URL, self.body, format="json").status_code, 429)


class GeneratedQuizValidationTests(TestCase):
    def assert_rejected(self, payload):
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        with self.assertRaises(generation.QuizGenerationError):
            generation.parse_generated_quiz(raw)

    def test_valid_payload_is_accepted(self):
        parsed = generation.parse_generated_quiz(json.dumps(valid_payload()))
        self.assertEqual(len(parsed["questions"]), 20)

    def test_malformed_payloads_are_rejected(self):
        self.assert_rejected("{")
        self.assert_rejected(valid_payload(count=4))
        self.assert_rejected(valid_payload(count=19))
        self.assert_rejected(valid_payload(count=21))
        mutations = {
            "three choices": lambda q: q.update(choices=q["choices"][:3]),
            "duplicate choices": lambda q: q.update(choices=["x", "x", "y", "z"]),
            "out of range index": lambda q: q.update(correct_index=4),
            "boolean index": lambda q: q.update(correct_index=True),
            "missing explanation": lambda q: q.update(explanation=" "),
            "empty text": lambda q: q.update(text=""),
        }
        for name, mutate in mutations.items():
            with self.subTest(name):
                payload = valid_payload()
                mutate(payload["questions"][0])
                self.assert_rejected(payload)

    def test_duplicate_questions_are_rejected(self):
        payload = valid_payload()
        payload["questions"][1]["text"] = payload["questions"][0]["text"]
        self.assert_rejected(payload)

    def test_accents_case_and_punctuation_do_not_hide_duplicates(self):
        payload = valid_payload()
        payload["questions"][0]["text"] = "Que renvoie `len([2, 4, 6])` ?"
        payload["questions"][1]["text"] = "QUE RENVOIE len([2,4,6])"
        self.assert_rejected(payload)

    def test_near_identical_rewording_is_rejected(self):
        payload = valid_payload()
        payload["questions"][0]["text"] = "Quelle est la valeur renvoyée par la fonction len appliquée à une liste de trois éléments ?"
        payload["questions"][1]["text"] = "Quelle est la valeur renvoyée par la fonction len appliquée à une liste de trois éléments"
        self.assert_rejected(payload)

    def test_distinct_questions_are_not_flagged_as_duplicates(self):
        payload = valid_payload()
        payload["questions"][0]["text"] = "Que renvoie `len([2, 4, 6])` dans Python 3 ?"
        payload["questions"][1]["text"] = "Quelle exception lève `int(\"abc\")` dans Python 3 ?"
        self.assertEqual(len(generation.parse_generated_quiz(json.dumps(payload))["questions"]), 20)

    def test_prompt_requests_exactly_twenty_questions(self):
        category = ChallengeCategory.objects.get(slug="python")
        prompt = generation.build_user_prompt(category, "BEGINNER")
        self.assertEqual(generation.QUESTION_COUNT, 20)
        self.assertIn("Nombre de questions : 20", prompt)
        self.assertIn("exactement 20 questions", prompt)

    def test_invalid_output_creates_no_choices(self):
        before = AnswerChoice.objects.count()
        self.assert_rejected(valid_payload(count=2))
        self.assertEqual(AnswerChoice.objects.count(), before)
