"""Suivi des interactions : sélections, changements, timeouts, métriques."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from challenges.models import QuestionInteraction, Quiz, QuizAttempt

User = get_user_model()


@override_settings(CHALLENGE_LLM_PROVIDER="mock", CHALLENGE_QUESTION_TIME_LIMIT_SECONDS=60)
class InteractionTrackingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="inter-user",
            email="inter-user@example.com",
            password="x" * 12,
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.quiz = Quiz.objects.filter(status="PUBLISHED", category__slug="python").first()
        started = self.client.post("/api/challenges/attempts/", {"quiz_id": self.quiz.pk}, format="json")
        self.attempt_id = started.data["id"]
        self.questions = list(self.quiz.questions.order_by("position"))
        self.base = f"/api/challenges/attempts/{self.attempt_id}"

    def event(self, question, event, choice=None):
        body = {"question_id": question.pk, "event": event}
        if choice is not None:
            body["choice_id"] = choice.pk
        return self.client.post(f"{self.base}/interactions/", body, format="json")

    def test_view_is_idempotent_and_starts_the_timer_once(self):
        q = self.questions[0]
        self.assertEqual(self.event(q, "view").status_code, 200)
        first = QuestionInteraction.objects.get(question=q).displayed_at
        self.event(q, "view")
        self.assertEqual(QuestionInteraction.objects.filter(question=q).count(), 1)
        self.assertEqual(QuestionInteraction.objects.get(question=q).displayed_at, first)

    def test_changes_count_only_different_selections(self):
        q = self.questions[0]
        a, b = list(q.choices.all()[:2])
        for choice in (a, a, b, b, a):
            self.event(q, "select", choice)
        interaction = QuestionInteraction.objects.get(question=q)
        self.assertEqual(interaction.answer_changes, 2)
        self.assertIsNotNone(interaction.first_selected_at)

    def test_total_answer_changes_accumulates_across_questions(self):
        first, second = self.questions[:2]
        first_choices = list(first.choices.all())
        second_choices = list(second.choices.all())
        for choice in (first_choices[0], first_choices[1], first_choices[1], first_choices[2]):
            self.event(first, "select", choice)
        for choice in (second_choices[0], second_choices[0], second_choices[1]):
            response = self.event(second, "select", choice)
        self.assertEqual(response.data["total_answer_changes"], 3)
        self.assertEqual(response.data["answer_changes"], 3)

    def test_timeout_recorded_once_and_only_after_the_limit(self):
        q = self.questions[0]
        self.event(q, "view")
        self.event(q, "timeout")
        self.assertFalse(QuestionInteraction.objects.get(question=q).timed_out)
        QuestionInteraction.objects.filter(question=q).update(
            displayed_at=timezone.now() - timedelta(seconds=61)
        )
        self.event(q, "timeout")
        first = QuestionInteraction.objects.get(question=q).timed_out_at
        response = self.event(q, "timeout")
        self.assertEqual(response.data["timeout_count"], 1)
        self.assertEqual(QuestionInteraction.objects.get(question=q).timed_out_at, first)

    def test_timeout_does_not_submit_an_answer_or_change_scoring(self):
        q = self.questions[0]
        self.event(q, "view")
        QuestionInteraction.objects.filter(question=q).update(
            displayed_at=timezone.now() - timedelta(seconds=120)
        )
        response = self.event(q, "timeout")
        self.assertEqual(response.data["submitted_answers"], 0)
        self.assertEqual(response.data["unanswered_questions"], 20)

    def test_metrics_come_from_persisted_answers(self):
        right, wrong = self.questions[0], self.questions[1]
        for q, correct in ((right, True), (wrong, False)):
            self.event(q, "view")
            choice = q.choices.filter(is_correct=correct).first()
            self.event(q, "select", choice)
            self.client.post(
                f"{self.base}/answers/",
                {"question_id": q.pk, "choice_id": choice.pk},
                format="json",
            )
        metrics = self.client.get(f"{self.base}/metrics/").data
        self.assertEqual(metrics["submitted_answers"], 2)
        self.assertEqual(metrics["correct_answers"], 1)
        self.assertEqual(metrics["incorrect_answers"], 1)
        self.assertEqual(metrics["accuracy_percent"], 50)
        self.assertEqual(metrics["unanswered_questions"], 18)
        self.assertIsNotNone(metrics["average_response_seconds"])
        self.assertNotIn("is_correct", str(metrics))

    def test_hesitation_indicators_are_separate_and_thresholded(self):
        q = self.questions[0]
        self.event(q, "view")
        choice = q.choices.first()
        self.event(q, "select", choice)
        QuestionInteraction.objects.filter(question=q).update(
            displayed_at=timezone.now() - timedelta(seconds=30)
        )
        metrics = self.client.get(f"{self.base}/metrics/").data
        self.assertEqual(metrics["hesitation"]["delayed_first_selection"], 1)
        self.assertEqual(metrics["hesitation"]["many_answer_changes"], 0)
        self.assertEqual(metrics["hesitation"]["long_response"], 0)

    def test_events_rejected_for_other_users_and_completed_attempts(self):
        other = User.objects.create_user(
            username="other-user",
            email="other-user@example.com",
            password="x" * 12,
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get_or_create(user=other)[0].key}")
        self.assertEqual(client.get(f"{self.base}/metrics/").status_code, 404)
        QuizAttempt.objects.filter(pk=self.attempt_id).update(status="COMPLETED")
        self.assertEqual(self.event(self.questions[0], "view").status_code, 409)

    def test_invalid_event_and_foreign_choice_are_rejected(self):
        q = self.questions[0]
        self.assertEqual(self.event(q, "bogus").status_code, 400)
        foreign = self.questions[1].choices.first()
        self.assertEqual(self.event(q, "select", foreign).status_code, 404)

    def test_events_after_answer_do_not_change_metrics(self):
        q = self.questions[0]
        choice = q.choices.first()
        self.event(q, "select", choice)
        self.client.post(
            f"{self.base}/answers/", {"question_id": q.pk, "choice_id": choice.pk}, format="json"
        )
        other = q.choices.exclude(pk=choice.pk).first()
        response = self.event(q, "select", other)
        self.assertEqual(response.data["answer_changes"], 0)
