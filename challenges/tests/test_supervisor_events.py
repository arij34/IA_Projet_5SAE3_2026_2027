"""Persistence and transaction tests for supervisor trigger events."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from challenges.models import (
    AnswerChoice,
    ChallengeCategory,
    Question,
    Quiz,
    QuizAttempt,
    SubmittedAnswer,
    SupervisorEvent,
)
from challenges.services.attempts import submit_answer
from challenges.services.supervisor_events import persist_eligible_supervisor_event
from challenges.services.supervisor_policy import (
    SupervisorTrigger,
    TriggerDecision,
)

BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class SupervisorEventPersistenceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="event-user",
            email="event-user@example.com",
            password="not-a-real-password",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        self.category = ChallengeCategory.objects.create(
            slug="event-category",
            name="Events",
            description="Test category",
        )
        self.quiz = Quiz.objects.create(
            category=self.category,
            title="Event test quiz",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.PUBLISHED,
        )
        self.questions = []
        for position in range(1, 6):
            question = Question.objects.create(
                quiz=self.quiz,
                text=f"Question {position}",
                position=position,
            )
            for choice_position in range(1, 5):
                AnswerChoice.objects.create(
                    question=question,
                    text=f"Choice {choice_position}",
                    position=choice_position,
                    is_correct=choice_position == 1,
                )
            self.questions.append(question)
        self.attempt = QuizAttempt.objects.create(
            user=self.user,
            quiz=self.quiz,
            total_questions=len(self.questions),
        )

    def submit(self, index, correct, seconds):
        question = self.questions[index]
        choice = (
            question.choices.get(is_correct=True)
            if correct
            else question.choices.filter(is_correct=False).first()
        )
        moment = BASE + timedelta(seconds=seconds)
        with patch("django.utils.timezone.now", return_value=moment):
            return submit_answer(self.attempt, question, choice)

    def submit_pattern(self, pattern, start_seconds=0, interval=10):
        answers = []
        for index, letter in enumerate(pattern):
            answers.append(
                self.submit(index, letter == "C", start_seconds + index * interval)
            )
        return answers

    def other_user(self):
        user_model = get_user_model()
        return user_model.objects.create_user(
            username="other-event-user",
            email="other-event-user@example.com",
            password="not-a-real-password",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )

    def make_event(self, attempt, answer, trigger, slot, created_at=None, event_key=None):
        event = SupervisorEvent.objects.create(
            attempt=attempt,
            source_answer=answer,
            trigger_type=trigger.value,
            event_key=event_key
            or f"{attempt.pk}:{trigger.value}:{answer.pk}",
            slot=slot,
        )
        if created_at is not None:
            SupervisorEvent.objects.filter(pk=event.pk).update(created_at=created_at)
            event.refresh_from_db()
        return event

    def test_no_eligible_trigger_creates_no_event(self):
        self.submit_pattern("WW")
        self.assertEqual(SupervisorEvent.objects.count(), 0)

    def test_three_consecutive_incorrect_answers_create_one_event(self):
        self.submit_pattern("WWW")

        event = SupervisorEvent.objects.get(attempt=self.attempt)
        self.assertEqual(event.trigger_type, SupervisorTrigger.REPEATED_ERRORS.value)
        self.assertEqual(event.source_answer_id, SubmittedAnswer.objects.order_by("pk").last().pk)
        self.assertEqual(event.slot, 1)
        self.assertEqual(
            SupervisorEvent.objects.filter(
                attempt=self.attempt,
                trigger_type=SupervisorTrigger.REPEATED_ERRORS.value,
            ).count(),
            1,
        )

    def test_three_consecutive_correct_answers_create_positive_event(self):
        self.submit_pattern("CCC")

        event = SupervisorEvent.objects.get(attempt=self.attempt)
        self.assertEqual(event.trigger_type, SupervisorTrigger.POSITIVE_FEEDBACK.value)

    def test_120_second_gap_creates_slow_progress_event(self):
        self.submit(0, True, 0)
        self.submit(1, False, 120)

        event = SupervisorEvent.objects.get(attempt=self.attempt)
        self.assertEqual(event.trigger_type, SupervisorTrigger.SLOW_PROGRESS.value)

    def test_correctness_trigger_has_priority_over_simultaneous_pacing(self):
        self.submit(0, False, 0)
        self.submit(1, False, 10)
        self.submit(2, False, 130)

        events = list(SupervisorEvent.objects.filter(attempt=self.attempt))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].trigger_type, SupervisorTrigger.REPEATED_ERRORS.value)

    def test_retry_does_not_create_an_additional_event(self):
        saved, created = self.submit_pattern("WWW")[-1]
        self.assertTrue(created)
        count_before = SupervisorEvent.objects.filter(attempt=self.attempt).count()

        answer, retry_created = self.submit(
            2,
            False,
            30,
        )

        self.assertFalse(retry_created)
        self.assertEqual(answer.pk, saved.pk)
        self.assertEqual(
            SupervisorEvent.objects.filter(attempt=self.attempt).count(),
            count_before,
        )

    def test_completed_attempt_cannot_create_new_event(self):
        self.submit_pattern("CCCCC")
        saved_answer = SubmittedAnswer.objects.filter(attempt=self.attempt).last()
        before = SupervisorEvent.objects.filter(attempt=self.attempt).count()
        self.attempt.status = QuizAttempt.Status.COMPLETED
        self.attempt.save(update_fields=("status",))

        with transaction.atomic():
            event = persist_eligible_supervisor_event(saved_answer)

        self.assertIsNone(event)
        self.assertEqual(SupervisorEvent.objects.filter(attempt=self.attempt).count(), before)

    def test_cooldown_blocks_at_119_seconds_and_allows_at_120(self):
        first, _ = self.submit(0, True, 0)
        prior = self.make_event(
            self.attempt,
            first,
            SupervisorTrigger.POSITIVE_FEEDBACK,
            slot=1,
            created_at=BASE + timedelta(seconds=1),
        )
        self.submit(1, False, 120)
        self.assertEqual(
            SupervisorEvent.objects.filter(attempt=self.attempt).count(),
            1,
            "The 119-second interval from the stored event must suppress pacing.",
        )

        second_attempt = QuizAttempt.objects.create(
            user=self.other_user(),
            quiz=self.quiz,
            total_questions=len(self.questions),
        )
        first_answer = SubmittedAnswer.objects.create(
            attempt=second_attempt,
            question=self.questions[0],
            selected_choice=self.questions[0].choices.get(is_correct=True),
            is_correct=True,
        )
        SubmittedAnswer.objects.filter(pk=first_answer.pk).update(submitted_at=BASE)
        first_answer.refresh_from_db()
        self.make_event(
            second_attempt,
            first_answer,
            SupervisorTrigger.POSITIVE_FEEDBACK,
            slot=1,
            created_at=BASE,
        )
        second_question = self.questions[1]
        wrong_choice = second_question.choices.filter(is_correct=False).first()
        with patch(
            "django.utils.timezone.now",
            return_value=BASE + timedelta(seconds=120),
        ):
            submit_answer(second_attempt, second_question, wrong_choice)

        self.assertEqual(
            SupervisorEvent.objects.filter(attempt=second_attempt).count(),
            2,
            "The exact 120-second interval must allow the pacing event.",
        )
        self.assertEqual(prior.trigger_type, SupervisorTrigger.POSITIVE_FEEDBACK.value)

    def test_two_event_limit_is_enforced_by_database_slot_constraint(self):
        first, _ = self.submit(0, False, 0)
        second, _ = self.submit(1, False, 10)
        self.make_event(
            self.attempt, first, SupervisorTrigger.POSITIVE_FEEDBACK, slot=1
        )
        self.make_event(self.attempt, second, SupervisorTrigger.SLOW_PROGRESS, slot=2)

        self.submit(2, False, 20)

        self.assertEqual(SupervisorEvent.objects.filter(attempt=self.attempt).count(), 2)

    def test_database_rejects_duplicate_event_key(self):
        first_attempt_answer, _ = self.submit(0, True, 0)
        event_key = f"{self.attempt.pk}:slow_progress:shared"
        self.make_event(
            self.attempt,
            first_attempt_answer,
            SupervisorTrigger.SLOW_PROGRESS,
            slot=1,
            event_key=event_key,
        )

        other_attempt = QuizAttempt.objects.create(
            user=self.other_user(),
            quiz=self.quiz,
            total_questions=len(self.questions),
        )
        other_answer = SubmittedAnswer.objects.create(
            attempt=other_attempt,
            question=self.questions[0],
            selected_choice=self.questions[0].choices.get(is_correct=True),
            is_correct=True,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_event(
                other_attempt,
                other_answer,
                SupervisorTrigger.SLOW_PROGRESS,
                slot=1,
                event_key=event_key,
            )

    def test_expected_duplicate_conflict_is_suppressed(self):
        first, _ = self.submit(0, True, 0)
        second, _ = self.submit(1, False, 10)
        duplicate = self.make_event(
            self.attempt,
            first,
            SupervisorTrigger.REPEATED_ERRORS,
            slot=1,
        )
        decision = TriggerDecision(
            SupervisorTrigger.REPEATED_ERRORS,
            event_key=duplicate.event_key,
        )

        with (
            patch(
                "challenges.services.supervisor_events.evaluate_answer_event",
                return_value=decision,
            ),
            patch(
                "challenges.services.supervisor_events.SupervisorEvent.objects.create",
                side_effect=IntegrityError(
                    "UNIQUE constraint failed: challenges_supervisorevent.event_key"
                ),
            ),
            transaction.atomic(),
        ):
            event = persist_eligible_supervisor_event(second)

        self.assertIsNone(event)
        self.assertEqual(SupervisorEvent.objects.filter(attempt=self.attempt).count(), 1)

    def test_unrelated_integrity_error_is_not_swallowed(self):
        first, _ = self.submit(0, True, 0)
        decision = TriggerDecision(
            SupervisorTrigger.REPEATED_ERRORS,
            event_key=f"{self.attempt.pk}:repeated_errors:unexpected",
        )

        with (
            patch(
                "challenges.services.supervisor_events.evaluate_answer_event",
                return_value=decision,
            ),
            patch(
                "challenges.services.supervisor_events.SupervisorEvent.objects.create",
                side_effect=IntegrityError(
                    "NOT NULL constraint failed: challenges_supervisorevent.trigger_type"
                ),
            ),
            transaction.atomic(),
        ):
            with self.assertRaises(IntegrityError):
                persist_eligible_supervisor_event(first)

    def test_database_rejects_second_event_for_same_trigger(self):
        first, _ = self.submit(0, True, 0)
        second, _ = self.submit(1, True, 10)
        self.make_event(
            self.attempt, first, SupervisorTrigger.POSITIVE_FEEDBACK, slot=1
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_event(
                self.attempt,
                second,
                SupervisorTrigger.POSITIVE_FEEDBACK,
                slot=2,
            )

    def test_database_rejects_two_triggers_for_one_source_answer(self):
        answer, _ = self.submit(0, True, 0)
        self.make_event(
            self.attempt, answer, SupervisorTrigger.SLOW_PROGRESS, slot=1
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_event(
                self.attempt,
                answer,
                SupervisorTrigger.REPEATED_ERRORS,
                slot=2,
            )

    def test_database_rejects_slot_greater_than_two(self):
        answer, _ = self.submit(0, True, 0)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_event(
                self.attempt,
                answer,
                SupervisorTrigger.POSITIVE_FEEDBACK,
                slot=3,
            )

    def test_cooldowns_are_independent_between_attempts(self):
        self.submit_pattern("WWW")
        other_attempt = QuizAttempt.objects.create(
            user=self.other_user(),
            quiz=self.quiz,
            total_questions=len(self.questions),
        )
        for index in range(3):
            question = self.questions[index]
            wrong_choice = question.choices.filter(is_correct=False).first()
            with patch(
                "django.utils.timezone.now",
                return_value=BASE + timedelta(seconds=10 * (index + 1)),
            ):
                submit_answer(other_attempt, question, wrong_choice)

        self.assertEqual(
            SupervisorEvent.objects.filter(
                attempt=other_attempt,
                trigger_type=SupervisorTrigger.REPEATED_ERRORS.value,
            ).count(),
            1,
        )

    def test_event_failure_keeps_answer_and_rolls_back_partial_event(self):
        self.submit_pattern("WW")
        from challenges.services import attempts

        persist = attempts.persist_eligible_supervisor_event

        def persist_then_fail(answer):
            persist(answer)
            raise RuntimeError("simulated event-write failure")

        with patch(
            "challenges.services.attempts.persist_eligible_supervisor_event",
            side_effect=persist_then_fail,
        ):
            with self.assertLogs("challenges.services.attempts", level="ERROR"):
                _, created = self.submit(2, False, 30)

        self.assertTrue(created)
        self.assertEqual(SubmittedAnswer.objects.filter(attempt=self.attempt).count(), 3)
        self.assertEqual(SupervisorEvent.objects.filter(attempt=self.attempt).count(), 0)

    def test_event_contains_no_answer_content_or_correctness(self):
        self.submit_pattern("WWW")
        self.assertEqual(SupervisorEvent.objects.filter(attempt=self.attempt).count(), 1)
        field_names = {field.name for field in SupervisorEvent._meta.fields}
        self.assertTrue(
            {
                "attempt",
                "source_answer",
                "trigger_type",
                "event_key",
                "slot",
                "created_at",
                "message",
                "prompt_version",
                "generation_status",
            }.issubset(field_names)
        )
        self.assertTrue(
            {"is_correct", "selected_choice", "question", "explanation", "user"}.isdisjoint(
                field_names
            )
        )
