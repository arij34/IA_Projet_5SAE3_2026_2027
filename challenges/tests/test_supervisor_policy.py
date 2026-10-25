"""Tests for the deterministic supervisor trigger policy; no network or LLM."""

from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from challenges.models import (
    AnswerChoice,
    ChallengeCategory,
    Question,
    Quiz,
    QuizAttempt,
    QuestionInteraction,
    SubmittedAnswer,
)
from challenges.services.attempts import complete_attempt, submit_answer
from challenges.services.supervisor_policy import (
    AnswerEvent,
    PriorIntervention,
    Suppression,
    SupervisorTrigger,
    build_event_key,
    evaluate_answer_event,
    evaluate_trigger,
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def seq(pattern, gaps=None):
    """Build answers from a string such as 'WWC' (W wrong, C correct)."""
    gaps = gaps or [10] * len(pattern)
    events, moment = [], T0
    for index, (char, gap) in enumerate(zip(pattern, gaps), start=1):
        moment = moment + timedelta(seconds=gap)
        events.append(AnswerEvent(index, char == "C", moment))
    return events


def decide(pattern, gaps=None, **kwargs):
    options = {"created": True, "attempt_completed": False, **kwargs}
    return evaluate_trigger(7, seq(pattern, gaps), **options)


class StreakPolicyTests(SimpleTestCase):
    def test_single_answer_infers_no_pattern(self):
        for pattern in ("W", "C"):
            self.assertIsNone(decide(pattern).trigger)

    def test_fewer_than_three_incorrect_does_not_trigger(self):
        self.assertIsNone(decide("WW").trigger)

    def test_three_consecutive_incorrect_triggers_repeated_errors(self):
        decision = decide("WWW")
        self.assertEqual(decision.trigger, SupervisorTrigger.REPEATED_ERRORS)
        self.assertEqual(decision.event_key, "7:repeated_errors:3")

    def test_correct_answer_breaks_incorrect_streak(self):
        self.assertIsNone(decide("WWCW").trigger)
        self.assertIsNone(decide("WWC").trigger)

    def test_fewer_than_three_correct_does_not_trigger(self):
        self.assertIsNone(decide("CC").trigger)

    def test_three_consecutive_correct_triggers_positive_feedback(self):
        self.assertEqual(decide("CCC").trigger, SupervisorTrigger.POSITIVE_FEEDBACK)

    def test_mixed_sequences_do_not_trigger(self):
        for pattern in ("CWC", "WCW", "CWCWC", "WCWCW"):
            with self.subTest(pattern=pattern):
                self.assertIsNone(decide(pattern).trigger)

    def test_streak_is_reported_only_on_its_third_answer(self):
        self.assertIsNone(decide("WWWW").trigger)
        self.assertEqual(decide("CWWW").trigger, SupervisorTrigger.REPEATED_ERRORS)

    def test_decision_exposes_no_correctness_or_answer_key(self):
        decision = decide("WWW")
        self.assertEqual(
            set(vars(decision)), {"trigger", "event_key", "suppressed_by"}
        )


class PacingPolicyTests(SimpleTestCase):
    def test_gap_of_exactly_120_seconds_triggers(self):
        decision = decide("CW", gaps=[10, 120])
        self.assertEqual(decision.trigger, SupervisorTrigger.SLOW_PROGRESS)

    def test_gap_below_120_seconds_does_not_trigger(self):
        self.assertIsNone(decide("CW", gaps=[10, 119]).trigger)

    def test_first_answer_has_no_previous_submission(self):
        self.assertIsNone(decide("C", gaps=[500]).trigger)

    def test_only_the_latest_gap_is_considered(self):
        self.assertIsNone(decide("CWC", gaps=[10, 300, 10]).trigger)

    def test_correctness_wins_over_simultaneous_pacing(self):
        decision = decide("WWW", gaps=[10, 10, 200])
        self.assertEqual(decision.trigger, SupervisorTrigger.REPEATED_ERRORS)
        decision = decide("CCC", gaps=[10, 10, 200])
        self.assertEqual(decision.trigger, SupervisorTrigger.POSITIVE_FEEDBACK)

    def test_pacing_is_used_when_correctness_candidate_is_suppressed(self):
        prior = [PriorIntervention(SupervisorTrigger.REPEATED_ERRORS, T0)]
        decision = decide("WWW", gaps=[10, 10, 200], prior_interventions=prior)
        self.assertEqual(decision.trigger, SupervisorTrigger.SLOW_PROGRESS)


class LifecyclePolicyTests(SimpleTestCase):
    def test_completed_attempt_emits_nothing(self):
        decision = decide("WWW", attempt_completed=True)
        self.assertIsNone(decision.trigger)
        self.assertEqual(decision.suppressed_by, (Suppression.ATTEMPT_COMPLETED,))

    def test_idempotent_retry_emits_nothing(self):
        decision = decide("WWW", created=False)
        self.assertIsNone(decision.trigger)
        self.assertEqual(decision.suppressed_by, (Suppression.NOT_NEW_ANSWER,))

    def test_empty_history_emits_nothing(self):
        decision = evaluate_trigger(1, [], created=True, attempt_completed=False)
        self.assertIsNone(decision.trigger)


class CooldownPolicyTests(SimpleTestCase):
    """Cooldown rules over explicitly supplied prior interventions."""

    def source_time(self, pattern, gaps=None):
        return seq(pattern, gaps)[-1].submitted_at

    def test_attempt_limit_of_two(self):
        prior = [
            PriorIntervention(SupervisorTrigger.SLOW_PROGRESS, T0),
            PriorIntervention(SupervisorTrigger.POSITIVE_FEEDBACK, T0),
        ]
        decision = decide("WWW", gaps=[10, 10, 500], prior_interventions=prior)
        self.assertIsNone(decision.trigger)
        self.assertEqual(decision.suppressed_by, (Suppression.ATTEMPT_LIMIT,))

    def test_one_intervention_per_trigger_type(self):
        prior = [PriorIntervention(SupervisorTrigger.REPEATED_ERRORS, T0)]
        decision = decide("WWW", gaps=[10, 10, 10], prior_interventions=prior)
        self.assertIsNone(decision.trigger)
        self.assertEqual(decision.suppressed_by, (Suppression.TRIGGER_ALREADY_USED,))

    def test_cooldown_blocks_below_120_seconds_and_allows_at_120(self):
        source = self.source_time("WWW", [10, 10, 10])
        blocked = [
            PriorIntervention(
                SupervisorTrigger.POSITIVE_FEEDBACK, source - timedelta(seconds=119)
            )
        ]
        allowed = [
            PriorIntervention(
                SupervisorTrigger.POSITIVE_FEEDBACK, source - timedelta(seconds=120)
            )
        ]
        denied = decide("WWW", prior_interventions=blocked)
        self.assertEqual(denied.suppressed_by, (Suppression.COOLDOWN,))
        self.assertEqual(
            decide("WWW", prior_interventions=allowed).trigger,
            SupervisorTrigger.REPEATED_ERRORS,
        )

    def test_event_identity_is_attempt_trigger_and_source_answer(self):
        key = build_event_key(4, SupervisorTrigger.SLOW_PROGRESS, 99)
        self.assertEqual(key, "4:slow_progress:99")
        self.assertEqual(decide("WWW").event_key, decide("WWW").event_key)


class PersistedAnswerEvaluationTests(TestCase):
    """The DB adapter, driven through the real answer-submission service."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="policy-user",
            email="policy-user@example.com",
            password="not-a-real-password",
            role=user_model.Role.FREELANCER,
            moderation_status=user_model.ModerationStatus.OK,
        )
        category = ChallengeCategory.objects.create(
            slug="policy-cat", name="Policy", description="d"
        )
        self.quiz = Quiz.objects.create(
            category=category,
            title="Policy quiz",
            difficulty=Quiz.Difficulty.BEGINNER,
            status=Quiz.Status.PUBLISHED,
        )
        self.questions = []
        for position in range(1, 6):
            question = Question.objects.create(
                quiz=self.quiz, text=f"Q{position}", position=position
            )
            for index in range(1, 5):
                AnswerChoice.objects.create(
                    question=question,
                    text=f"c{index}",
                    position=index,
                    is_correct=index == 1,
                )
            self.questions.append(question)
        self.attempt = QuizAttempt.objects.create(
            user=self.user, quiz=self.quiz, total_questions=5
        )

    def answer(self, index, correct, seconds):
        """Submit through the service, then pin the timestamp deterministically."""
        question = self.questions[index]
        choices = question.choices
        choice = choices.get(is_correct=True) if correct else choices.filter(is_correct=False).first()
        saved, created = submit_answer(self.attempt, question, choice)
        if created:
            SubmittedAnswer.objects.filter(pk=saved.pk).update(
                submitted_at=T0 + timedelta(seconds=seconds)
            )
            saved.refresh_from_db()
        return saved, created

    def test_three_wrong_answers_trigger_after_third_new_answer(self):
        decisions = [
            evaluate_answer_event(*self.answer(i, False, 10 * (i + 1)))
            for i in range(3)
        ]
        self.assertEqual([d.trigger for d in decisions[:2]], [None, None])
        self.assertEqual(decisions[2].trigger, SupervisorTrigger.REPEATED_ERRORS)
        self.assertEqual(
            decisions[2].event_key,
            build_event_key(
                self.attempt.pk,
                SupervisorTrigger.REPEATED_ERRORS,
                SubmittedAnswer.objects.order_by("pk").last().pk,
            ),
        )

    def test_idempotent_retry_does_not_trigger_again(self):
        for i in range(3):
            self.answer(i, False, 10 * (i + 1))
        retry, created = submit_answer(
            self.attempt,
            self.questions[2],
            self.questions[2].choices.filter(is_correct=False).first(),
        )
        self.assertFalse(created)
        decision = evaluate_answer_event(retry, created)
        self.assertEqual(decision.suppressed_by, (Suppression.NOT_NEW_ANSWER,))
        self.assertEqual(SubmittedAnswer.objects.filter(attempt=self.attempt).count(), 3)

    def test_pacing_uses_persisted_submission_times(self):
        self.answer(0, True, 10)
        decision = evaluate_answer_event(*self.answer(1, False, 10 + 120))
        self.assertEqual(decision.trigger, SupervisorTrigger.SLOW_PROGRESS)

    def test_later_answers_do_not_change_an_earlier_decision(self):
        for i in range(3):
            saved, created = self.answer(i, True, 10 * (i + 1))
        self.answer(3, False, 100)
        self.assertEqual(
            evaluate_answer_event(saved, True).trigger,
            SupervisorTrigger.POSITIVE_FEEDBACK,
        )

    def test_completed_attempt_emits_nothing(self):
        saved = None
        for i in range(5):
            saved, _ = self.answer(i, False, 10 * (i + 1))
        complete_attempt(self.attempt)
        decision = evaluate_answer_event(saved, True)
        self.assertEqual(decision.suppressed_by, (Suppression.ATTEMPT_COMPLETED,))

    def test_other_attempts_answers_are_ignored(self):
        other = get_user_model().objects.create_user(
            username="policy-other",
            email="policy-other@example.com",
            password="not-a-real-password",
            role="FREELANCER",
            moderation_status="OK",
        )
        other_attempt = QuizAttempt.objects.create(
            user=other, quiz=self.quiz, total_questions=5
        )
        for i in range(2):
            question = self.questions[i]
            submit_answer(
                other_attempt, question, question.choices.filter(is_correct=False).first()
            )
        decision = evaluate_answer_event(*self.answer(0, False, 10))
        self.assertIsNone(decision.trigger)

    def test_repeated_changes_trigger_from_persisted_interaction(self):
        answer, created = self.answer(0, True, 50)
        QuestionInteraction.objects.create(
            attempt=self.attempt, question=self.questions[0],
            displayed_at=T0, first_selected_at=T0, answer_changes=3,
            last_selected_choice_id=self.questions[0].choices.first().pk,
        )
        decision = evaluate_answer_event(answer, created)
        self.assertEqual(decision.trigger, SupervisorTrigger.REPEATED_ANSWER_CHANGES)

    def test_long_response_and_multiple_timeouts_trigger_from_persisted_rows(self):
        answer, created = self.answer(0, True, 50)
        QuestionInteraction.objects.create(
            attempt=self.attempt, question=self.questions[0], displayed_at=T0,
        )
        QuestionInteraction.objects.create(
            attempt=self.attempt, question=self.questions[1], displayed_at=T0,
            timed_out=True, timed_out_at=T0,
        )
        QuestionInteraction.objects.create(
            attempt=self.attempt, question=self.questions[2], displayed_at=T0,
            timed_out=True, timed_out_at=T0,
        )
        decision = evaluate_answer_event(answer, created)
        self.assertEqual(decision.trigger, SupervisorTrigger.MULTIPLE_TIMEOUTS)

    def test_multiple_timeouts_trigger_when_response_is_not_long(self):
        answer, created = self.answer(0, True, 20)
        QuestionInteraction.objects.create(
            attempt=self.attempt, question=self.questions[0], displayed_at=T0,
        )
        for question in self.questions[1:3]:
            QuestionInteraction.objects.create(
                attempt=self.attempt, question=question, displayed_at=T0,
                timed_out=True, timed_out_at=T0,
            )
        decision = evaluate_answer_event(answer, created)
        self.assertEqual(decision.trigger, SupervisorTrigger.MULTIPLE_TIMEOUTS)

    def test_repeated_error_rule_keeps_priority_over_interaction_signals(self):
        decisions = []
        for index in range(3):
            answer, created = self.answer(index, False, 20 * (index + 1))
            if index == 2:
                QuestionInteraction.objects.create(
                    attempt=self.attempt, question=self.questions[index],
                    displayed_at=T0, answer_changes=3,
                )
            decisions.append(evaluate_answer_event(answer, created))
        self.assertEqual(decisions[-1].trigger, SupervisorTrigger.REPEATED_ERRORS)
