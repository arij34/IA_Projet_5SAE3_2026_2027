"""Tests des permissions et serializers publics Challenges."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from challenges.models import AnswerChoice, ChallengeCategory, Question, Quiz


User = get_user_model()


class ChallengeCatalogApiTests(TestCase):
    """Vérifie le catalogue, les quiz publiés et le masquage des réponses."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="challenge-user",
            email="challenge-user@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        self.pending_user = User.objects.create_user(
            username="challenge-pending",
            email="challenge-pending@example.com",
            password="MotDePasseFort!123",
            role=User.Role.FREELANCER,
        )
        self.owner = User.objects.create_user(
            username="challenge-owner",
            email="challenge-owner@example.com",
            password="MotDePasseFort!123",
            role=User.Role.PROJECT_OWNER,
            moderation_status=User.ModerationStatus.OK,
        )
        self.admin = User.objects.create_user(
            username="challenge-admin",
            email="challenge-admin@example.com",
            password="MotDePasseFort!123",
            role=User.Role.ADMIN,
            moderation_status=User.ModerationStatus.OK,
        )
        self.category = ChallengeCategory.objects.get(slug="python")

    def authenticate(self, user=None):
        token, _ = Token.objects.get_or_create(user=user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def create_quiz(self, status_value):
        quiz = Quiz.objects.create(
            category=self.category,
            title=f"Quiz {status_value}",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=status_value,
        )
        question = Question.objects.create(
            quiz=quiz,
            text="Quelle instruction affiche un texte en Python ?",
            position=1,
            explanation="La fonction print écrit une valeur dans la sortie.",
        )
        AnswerChoice.objects.create(
            question=question,
            text="print()",
            position=1,
            is_correct=True,
        )
        AnswerChoice.objects.create(
            question=question,
            text="echo()",
            position=2,
        )
        return quiz

    def assert_all_endpoints(self, user, expected_status):
        quiz = self.create_quiz(Quiz.Status.PUBLISHED)
        if user is None:
            self.client.credentials()
        else:
            self.authenticate(user)
        endpoints = (
            "/api/challenges/categories/",
            "/api/challenges/quizzes/",
            f"/api/challenges/quizzes/{quiz.pk}/",
        )
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint, user=user):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, expected_status)

    def test_anonymous_cannot_list_categories(self):
        self.assert_all_endpoints(None, status.HTTP_401_UNAUTHORIZED)

    def test_unapproved_user_cannot_list_categories(self):
        self.assert_all_endpoints(self.pending_user, status.HTTP_403_FORBIDDEN)

    def test_approved_project_owner_cannot_access_challenges(self):
        self.assert_all_endpoints(self.owner, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_access_freelancer_challenges(self):
        self.assert_all_endpoints(self.admin, status.HTTP_403_FORBIDDEN)

    def test_approved_freelancer_can_access_all_challenges_endpoints(self):
        self.assert_all_endpoints(self.user, status.HTTP_200_OK)

    def test_approved_user_gets_active_seeded_categories_and_difficulties(self):
        self.authenticate()
        ChallengeCategory.objects.create(
            slug="inactive",
            name="Inactive",
            description="Ne doit pas apparaître.",
            is_active=False,
        )

        response = self.client.get("/api/challenges/categories/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        category = next(item for item in response.data if item["slug"] == "python")
        self.assertEqual(category["description"], self.category.description)
        self.assertEqual(
            [item["value"] for item in category["difficulties"]],
            ["BEGINNER", "INTERMEDIATE", "ADVANCED"],
        )
        self.assertNotIn("inactive", [item["slug"] for item in response.data])

    def test_quiz_list_returns_only_published_and_supports_filters(self):
        self.authenticate()
        self.create_quiz(Quiz.Status.PUBLISHED)
        self.create_quiz(Quiz.Status.DRAFT)

        response = self.client.get(
            "/api/challenges/quizzes/?category=python&difficulty=BEGINNER"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = {item["title"] for item in response.data}
        self.assertIn("Quiz PUBLISHED", titles)
        self.assertNotIn("Quiz DRAFT", titles)
        self.assertNotIn("Python : les fondamentaux", titles)
        self.assertTrue(all(item["category"] == "python" for item in response.data))
        self.assertTrue(all(item["question_count"] >= 1 for item in response.data))

    def test_invalid_difficulty_returns_400(self):
        self.authenticate()

        response = self.client.get("/api/challenges/quizzes/?difficulty=EXPERT")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_quiz_detail_never_exposes_answer_or_explanation(self):
        self.authenticate()
        quiz = self.create_quiz(Quiz.Status.PUBLISHED)

        response = self.client.get(f"/api/challenges/quizzes/{quiz.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question = response.data["questions"][0]
        self.assertNotIn("explanation", question)
        self.assertNotIn("is_correct", question)
        self.assertNotIn("is_correct", question["choices"][0])
        self.assertEqual(len(question["choices"]), 2)

    def test_draft_quiz_is_not_retrievable(self):
        self.authenticate()
        quiz = self.create_quiz(Quiz.Status.DRAFT)

        response = self.client.get(f"/api/challenges/quizzes/{quiz.pk}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)