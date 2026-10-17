"""Tests for the authenticated, server-scored quiz attempt lifecycle."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from challenges.models import (
    AnswerChoice,
    Question,
    Quiz,
    QuizAttempt,
    SubmittedAnswer,
)


User = get_user_model()


class QuizAttemptApiTests(TestCase):
    """Verify attempt ownership, answer validation, completion and results."""

    def setUp(self):
        self.client = APIClient()
        self.freelancer = self.create_user(
            "attempt-freelancer",
            User.Role.FREELANCER,
            User.ModerationStatus.OK,
        )
        self.other_freelancer = self.create_user(
            "attempt-other",
            User.Role.FREELANCER,
            User.ModerationStatus.OK,
        )
        self.pending_freelancer = self.create_user(
            "attempt-pending",
            User.Role.FREELANCER,
            User.ModerationStatus.PENDING,
        )
        self.owner = self.create_user(
            "attempt-owner",
            User.Role.PROJECT_OWNER,
            User.ModerationStatus.OK,
        )
        self.admin = self.create_user(
            "attempt-admin",
            User.Role.ADMIN,
            User.ModerationStatus.OK,
        )
        self.quiz = Quiz.objects.get(title="Python : les fondamentaux")
        self.questions = list(
            self.quiz.questions.prefetch_related("choices").order_by("position")
        )

    def create_user(self, username, role, moderation_status):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="MotDePasseFort!123",
            role=role,
            moderation_status=moderation_status,
        )

    def authenticate(self, user=None):
        token, _ = Token.objects.get_or_create(user=user or self.freelancer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def start_attempt(self):
        return self.client.post(
            "/api/challenges/attempts/",
            {"quiz_id": self.quiz.pk},
            format="json",
        )

    def submit_answer(self, attempt_id, question, choice):
        return self.client.post(
            f"/api/challenges/attempts/{attempt_id}/answers/",
            {"question_id": question.pk, "choice_id": choice.pk},
            format="json",
        )

    def test_answer_is_saved_when_supervisor_event_persistence_fails(self):
        from unittest.mock import patch

        from django.db import OperationalError

        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        question = self.questions[0]
        choice = question.choices.first()

        with patch(
            "challenges.services.attempts.persist_eligible_supervisor_event",
            side_effect=OperationalError("no such table: challenges_supervisorevent"),
        ):
            with self.assertLogs("challenges.services.attempts", level="ERROR"):
                response = self.submit_answer(attempt_id, question, choice)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            SubmittedAnswer.objects.filter(
                attempt_id=attempt_id, question=question, selected_choice=choice
            ).exists()
        )

    def test_answer_is_saved_when_supervisor_processing_fails(self):
        from unittest.mock import patch

        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        question = self.questions[0]
        choice = question.choices.first()

        with patch("challenges.views.SupervisorEvent") as event_model:
            event_model.objects.filter.side_effect = RuntimeError("supervisor down")
            with self.assertLogs("challenges.views", level="ERROR"):
                response = self.submit_answer(attempt_id, question, choice)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["answered_count"], 1)
        self.assertEqual(SubmittedAnswer.objects.filter(attempt_id=attempt_id).count(), 1)

    def test_anonymous_is_rejected_from_attempt_endpoints(self):
        endpoints = (
            ("post", "/api/challenges/attempts/", {"quiz_id": self.quiz.pk}),
            ("get", "/api/challenges/attempts/1/", None),
            ("post", "/api/challenges/attempts/1/answers/", {}),
            ("post", "/api/challenges/attempts/1/complete/", {}),
            ("get", "/api/challenges/attempts/1/results/", None),
        )
        for method, path, payload in endpoints:
            with self.subTest(path=path):
                response = getattr(self.client, method)(
                    path,
                    payload,
                    format="json" if payload is not None else None,
                )
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unapproved_freelancer_cannot_start_attempt(self):
        self.authenticate(self.pending_freelancer)

        response = self.start_attempt()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_owner_and_admin_cannot_start_attempt(self):
        for user in (self.owner, self.admin):
            with self.subTest(role=user.role):
                self.authenticate(user)
                response = self.start_attempt()
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_start_resumes_existing_attempt_without_answer_key(self):
        self.authenticate()

        first = self.start_attempt()
        second = self.start_attempt()

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(QuizAttempt.objects.filter(user=self.freelancer).count(), 1)
        self.assertEqual(first.data["total_questions"], len(self.questions))
        for question in first.data["questions"]:
            self.assertNotIn("is_correct", question)
            self.assertNotIn("explanation", question)
            self.assertIsNone(question["selected_choice_id"])
            for choice in question["choices"]:
                self.assertNotIn("is_correct", choice)

    def test_draft_quiz_cannot_be_started(self):
        self.authenticate()
        draft = Quiz.objects.create(
            category=self.quiz.category,
            title="Draft quiz",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.DRAFT,
        )

        response = self.client.post(
            "/api/challenges/attempts/",
            {"quiz_id": draft.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempt_is_private_to_its_owner(self):
        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        self.authenticate(self.other_freelancer)

        responses = (
            self.client.get(f"/api/challenges/attempts/{attempt_id}/"),
            self.client.post(
                f"/api/challenges/attempts/{attempt_id}/answers/",
                {
                    "question_id": self.questions[0].pk,
                    "choice_id": self.questions[0].choices.first().pk,
                },
                format="json",
            ),
            self.client.post(f"/api/challenges/attempts/{attempt_id}/complete/"),
            self.client.get(f"/api/challenges/attempts/{attempt_id}/results/"),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_question_and_choice_must_belong_to_attempt_quiz(self):
        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        other_quiz = Quiz.objects.create(
            category=self.quiz.category,
            title="Other quiz",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.PUBLISHED,
        )
        other_question = Question.objects.create(
            quiz=other_quiz,
            text="Question extérieure",
            position=1,
        )
        other_choice = AnswerChoice.objects.create(
            question=other_question,
            text="Choix extérieur",
            position=1,
        )

        foreign_question = self.submit_answer(
            attempt_id,
            other_question,
            other_choice,
        )
        foreign_choice = self.submit_answer(
            attempt_id,
            self.questions[0],
            other_choice,
        )

        self.assertEqual(foreign_question.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign_choice.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_answer_retry_is_idempotent_and_conflicting_retry_is_rejected(self):
        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        question = self.questions[0]
        correct_choice = question.choices.get(is_correct=True)
        wrong_choice = question.choices.exclude(pk=correct_choice.pk).first()

        first = self.submit_answer(attempt_id, question, correct_choice)
        retry = self.submit_answer(attempt_id, question, correct_choice)
        conflict = self.submit_answer(attempt_id, question, wrong_choice)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertTrue(retry.data["already_submitted"])
        self.assertEqual(conflict.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(SubmittedAnswer.objects.filter(attempt_id=attempt_id).count(), 1)
        self.assertNotIn("is_correct", first.data)

    def test_incomplete_attempt_cannot_be_completed_or_viewed_as_results(self):
        self.authenticate()
        attempt_id = self.start_attempt().data["id"]

        completed = self.client.post(
            f"/api/challenges/attempts/{attempt_id}/complete/"
        )
        results = self.client.get(f"/api/challenges/attempts/{attempt_id}/results/")

        self.assertEqual(completed.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(results.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            QuizAttempt.objects.get(pk=attempt_id).status,
            QuizAttempt.Status.IN_PROGRESS,
        )

    def test_score_is_server_calculated_and_results_unlock_on_completion(self):
        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        correct_count = 0
        for index, question in enumerate(self.questions):
            correct_choice = question.choices.get(is_correct=True)
            if index < 2:
                choice = correct_choice
                correct_count += 1
            else:
                choice = question.choices.exclude(pk=correct_choice.pk).first()
            response = self.submit_answer(attempt_id, question, choice)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertNotIn("is_correct", response.data)

        before_completion = self.client.get(
            f"/api/challenges/attempts/{attempt_id}/results/"
        )
        self.assertEqual(before_completion.status_code, status.HTTP_409_CONFLICT)

        completion = self.client.post(
            f"/api/challenges/attempts/{attempt_id}/complete/"
        )
        result = self.client.get(f"/api/challenges/attempts/{attempt_id}/results/")

        self.assertEqual(completion.status_code, status.HTTP_200_OK)
        self.assertEqual(completion.data["status"], QuizAttempt.Status.COMPLETED)
        self.assertEqual(completion.data["correct_answers"], correct_count)
        self.assertEqual(completion.data["score_percent"], round(correct_count * 100 / len(self.questions)))
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(len(result.data["answers"]), len(self.questions))
        self.assertTrue(any(answer["is_correct"] for answer in result.data["answers"]))
        self.assertTrue(all("explanation" in answer for answer in result.data["answers"]))

    def test_completing_attempt_twice_returns_same_final_score(self):
        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        for question in self.questions:
            self.submit_answer(attempt_id, question, question.choices.get(is_correct=True))

        first = self.client.post(f"/api/challenges/attempts/{attempt_id}/complete/")
        second = self.client.post(f"/api/challenges/attempts/{attempt_id}/complete/")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["score_percent"], 100)
        self.assertEqual(second.data["score_percent"], first.data["score_percent"])

    def test_completed_attempt_rejects_new_answers(self):
        self.authenticate()
        attempt_id = self.start_attempt().data["id"]
        for question in self.questions:
            self.submit_answer(attempt_id, question, question.choices.get(is_correct=True))
        self.client.post(f"/api/challenges/attempts/{attempt_id}/complete/")

        response = self.submit_answer(
            attempt_id,
            self.questions[0],
            self.questions[0].choices.get(is_correct=True),
        )

