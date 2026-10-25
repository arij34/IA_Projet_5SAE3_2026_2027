"""Invariants of the curated catalog: every published quiz has exactly 20 valid questions."""

import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from challenges.curated_quizzes import CURATED_QUIZZES, QUESTIONS_PER_QUIZ
from challenges.models import Quiz
from challenges.services import generation

User = get_user_model()


class CuratedRegistryTests(SimpleTestCase):
    def test_registry_covers_existing_levels_and_new_advanced_categories(self):
        self.assertEqual(len(CURATED_QUIZZES), 15)
        expected = {
            (slug, difficulty)
            for slug in ("python", "django", "react", "typescript")
            for difficulty in ("BEGINNER", "INTERMEDIATE", "ADVANCED")
        }
        expected.update(
            (slug, "ADVANCED") for slug in ("javascript", "sql", "git")
        )
        self.assertEqual(
            {(slug, difficulty) for slug, difficulty, _, _ in CURATED_QUIZZES},
            expected,
        )

    def test_each_quiz_passes_the_generation_validator_with_exactly_20_questions(self):
        self.assertEqual(QUESTIONS_PER_QUIZ, generation.QUESTION_COUNT)
        for slug, difficulty, title, payload in CURATED_QUIZZES:
            with self.subTest(slug=slug, difficulty=difficulty):
                parsed = generation.parse_generated_quiz(json.dumps(payload))
                self.assertEqual(len(parsed["questions"]), 20)

    def test_no_duplicate_questions_within_or_across_quizzes(self):
        seen = {}
        for slug, difficulty, _, payload in CURATED_QUIZZES:
            for item in payload["questions"]:
                key = generation._normalize(item["text"])
                self.assertNotIn(key, seen, f"{slug}/{difficulty} duplicates {seen.get(key)}")
                seen[key] = f"{slug}/{difficulty}"

    def test_correct_answer_position_is_balanced(self):
        for slug, difficulty, _, payload in CURATED_QUIZZES:
            positions = [item["correct_index"] for item in payload["questions"]]
            with self.subTest(slug=slug, difficulty=difficulty):
                self.assertEqual([positions.count(i) for i in range(4)], [5, 5, 5, 5])

    def test_no_placeholder_content(self):
        for _, _, title, payload in CURATED_QUIZZES:
            blob = json.dumps(payload, ensure_ascii=False).casefold()
            for marker in ("simulé", "lorem", "todo", "placeholder"):
                self.assertNotIn(marker, blob, f"{title}: {marker}")


class PublishedCatalogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="curated-user",
            email="curated-user@example.com",
            password="x" * 12,
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_every_published_quiz_has_exactly_20_valid_questions(self):
        published = Quiz.objects.filter(status=Quiz.Status.PUBLISHED)
        self.assertEqual(published.count(), 15)
        for quiz in published:
            questions = list(quiz.questions.prefetch_related("choices"))
            with self.subTest(quiz=quiz.title):
                self.assertEqual(len(questions), 20)
                for question in questions:
                    self.assertEqual(question.choices.count(), 4)
                    self.assertEqual(question.choices.filter(is_correct=True).count(), 1)
                    self.assertTrue(question.explanation.strip())

    def test_quizzes_have_the_expected_category_and_difficulty(self):
        for slug, difficulty, title, _ in CURATED_QUIZZES:
            with self.subTest(slug=slug, difficulty=difficulty):
                quiz = Quiz.objects.get(title=title)
                self.assertEqual(quiz.category.slug, slug)
                self.assertEqual(quiz.difficulty, difficulty)
                self.assertEqual(quiz.status, Quiz.Status.PUBLISHED)

    def test_legacy_incomplete_quiz_is_unpublished_not_deleted(self):
        legacy = Quiz.objects.get(title="Python : les fondamentaux")
        self.assertEqual(legacy.status, Quiz.Status.DRAFT)
        self.assertEqual(legacy.questions.count(), 3)

    def test_api_exposes_20_questions_without_answer_key(self):
        for slug, difficulty, _, _ in CURATED_QUIZZES:
            response = self.client.get(
                f"/api/challenges/quizzes/?category={slug}&difficulty={difficulty}"
            )
            with self.subTest(slug=slug, difficulty=difficulty):
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 1)
                detail = self.client.get(f"/api/challenges/quizzes/{response.data[0]['id']}/")
                self.assertEqual(len(detail.data["questions"]), 20)
                self.assertNotIn("is_correct", json.dumps(detail.data))

    def test_curated_quiz_can_be_completed_and_scored_across_all_20_questions(self):
        quiz = Quiz.objects.get(title=CURATED_QUIZZES[0][2])
        started = self.client.post(
            "/api/challenges/attempts/",
            {"quiz_id": quiz.pk},
            format="json",
        )
        self.assertEqual(started.status_code, 201)
        attempt_id = started.data["id"]
        self.assertEqual(started.data["total_questions"], 20)

        for question in quiz.questions.order_by("position"):
            response = self.client.post(
                f"/api/challenges/attempts/{attempt_id}/answers/",
                {
                    "question_id": question.pk,
                    "choice_id": question.choices.get(is_correct=True).pk,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertNotIn("is_correct", response.data)

        results_url = f"/api/challenges/attempts/{attempt_id}/results/"
        self.assertEqual(self.client.get(results_url).status_code, 409)
        completed = self.client.post(
            f"/api/challenges/attempts/{attempt_id}/complete/"
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["correct_answers"], 20)
        self.assertEqual(completed.data["score_percent"], 100)

        results = self.client.get(results_url)
        self.assertEqual(results.status_code, 200)
        self.assertEqual(len(results.data["answers"]), 20)
        self.assertTrue(all(item["is_correct"] for item in results.data["answers"]))
        self.assertTrue(all(item["explanation"] for item in results.data["answers"]))
