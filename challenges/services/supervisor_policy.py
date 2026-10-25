"""Deterministic, provisional trigger policy for the quiz supervisor.

The policy only decides whether an intervention is *eligible*. It never calls an
LLM, never persists anything and never exposes correctness or answer keys: a
decision carries only a trigger type and an event identity.

Cross-request cooldown and duplicate suppression need persisted supervisor
events, which do not exist yet. Callers must pass previously emitted
interventions explicitly; ``evaluate_answer_event`` does not infer them.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Sequence

from django.conf import settings

from challenges.models import QuestionInteraction, QuizAttempt, SubmittedAnswer

SLOW_PROGRESS_SECONDS = 120
STREAK_LENGTH = 3
MAX_INTERVENTIONS_PER_ATTEMPT = 2
MIN_SECONDS_BETWEEN_INTERVENTIONS = 120


class SupervisorTrigger(str, Enum):
    """Trigger types, listed in priority order (correctness before pacing)."""

    REPEATED_ERRORS = "repeated_errors"
    POSITIVE_FEEDBACK = "positive_feedback"
    SLOW_PROGRESS = "slow_progress"
    REPEATED_ANSWER_CHANGES = "repeated_answer_changes"
    LONG_RESPONSE = "long_response"
    MULTIPLE_TIMEOUTS = "multiple_timeouts"


class Suppression(str, Enum):
    """Why no intervention is eligible."""

    NOT_NEW_ANSWER = "not_new_answer"
    ATTEMPT_COMPLETED = "attempt_completed"
    NO_QUALIFYING_PATTERN = "no_qualifying_pattern"
    ATTEMPT_LIMIT = "attempt_limit"
    TRIGGER_ALREADY_USED = "trigger_already_used"
    COOLDOWN = "cooldown"


@dataclass(frozen=True)
class AnswerEvent:
    """Minimal server-side facts about one persisted answer."""

    answer_id: int
    is_correct: bool
    submitted_at: datetime


@dataclass(frozen=True)
class PriorIntervention:
    """An intervention already emitted for the attempt."""

    trigger: SupervisorTrigger
    created_at: datetime


@dataclass(frozen=True)
class TriggerDecision:
    """Outcome of the policy; ``trigger`` is None when no intervention is eligible."""

    trigger: SupervisorTrigger | None
    event_key: str | None = None
    suppressed_by: tuple[Suppression, ...] = ()


def build_event_key(attempt_id: int, trigger: SupervisorTrigger, answer_id: int) -> str:
    """Stable identity derived from attempt, trigger type and source answer."""
    return f"{attempt_id}:{trigger.value}:{answer_id}"


def _qualifying_triggers(answers: Sequence[AnswerEvent]) -> list[SupervisorTrigger]:
    """Return candidate triggers for the newest answer, in priority order."""
    candidates: list[SupervisorTrigger] = []
    # Exactly the third answer of a streak, so one long streak is not re-reported
    # on every later answer.
    streak = 0
    for event in reversed(answers):
        if event.is_correct == answers[-1].is_correct:
            streak += 1
        else:
            break
    if streak == STREAK_LENGTH:
        candidates.append(
            SupervisorTrigger.POSITIVE_FEEDBACK
            if answers[-1].is_correct
            else SupervisorTrigger.REPEATED_ERRORS
        )
    if len(answers) >= 2:
        gap = answers[-1].submitted_at - answers[-2].submitted_at
        if gap >= timedelta(seconds=SLOW_PROGRESS_SECONDS):
            candidates.append(SupervisorTrigger.SLOW_PROGRESS)
    return candidates


def evaluate_trigger(
    attempt_id: int,
    answers: Sequence[AnswerEvent],
    *,
    created: bool,
    attempt_completed: bool,
    prior_interventions: Sequence[PriorIntervention] = (),
    contextual_triggers: Sequence[SupervisorTrigger] = (),
) -> TriggerDecision:
    """Decide the eligible intervention for the newest answer in ``answers``.

    ``answers`` must be in submission order and end with the source answer.
    At most one trigger is returned; correctness signals win over pacing, and a
    suppressed higher-priority candidate falls through to the next one.
    """
    if not created:
        return TriggerDecision(None, suppressed_by=(Suppression.NOT_NEW_ANSWER,))
    if attempt_completed:
        return TriggerDecision(None, suppressed_by=(Suppression.ATTEMPT_COMPLETED,))
    if not answers:
        return TriggerDecision(None, suppressed_by=(Suppression.NO_QUALIFYING_PATTERN,))

    candidates = _qualifying_triggers(answers)
    # Correctness retains priority; contextual signals are evaluated from the
    # persisted interaction rows associated with the latest answer.
    candidates.extend(trigger for trigger in contextual_triggers if trigger not in candidates)
    if not candidates:
        return TriggerDecision(None, suppressed_by=(Suppression.NO_QUALIFYING_PATTERN,))
    if len(prior_interventions) >= MAX_INTERVENTIONS_PER_ATTEMPT:
        return TriggerDecision(None, suppressed_by=(Suppression.ATTEMPT_LIMIT,))

    source = answers[-1]
    used = {prior.trigger for prior in prior_interventions}
    cooldown = timedelta(seconds=MIN_SECONDS_BETWEEN_INTERVENTIONS)
    in_cooldown = any(
        source.submitted_at - prior.created_at < cooldown
        for prior in prior_interventions
    )
    suppressed: list[Suppression] = []
    for trigger in candidates:
        if trigger in used:
            suppressed.append(Suppression.TRIGGER_ALREADY_USED)
        elif in_cooldown:
            suppressed.append(Suppression.COOLDOWN)
        else:
            return TriggerDecision(
                trigger,
                event_key=build_event_key(attempt_id, trigger, source.answer_id),
            )
    return TriggerDecision(None, suppressed_by=tuple(suppressed))


def evaluate_answer_event(
    answer: SubmittedAnswer,
    created: bool,
    prior_interventions: Sequence[PriorIntervention] = (),
) -> TriggerDecision:
    """Evaluate a just-saved answer using persisted server-side attempt data.

    ``created`` is the flag returned by ``attempts.submit_answer``. Answers
    submitted after ``answer`` are ignored so the decision is reproducible.
    """
    attempt_id = answer.attempt_id
    status = QuizAttempt.objects.values_list("status", flat=True).get(pk=attempt_id)
    rows = (
        SubmittedAnswer.objects.filter(attempt_id=attempt_id)
        .order_by("submitted_at", "pk")
        .values_list("pk", "is_correct", "submitted_at")
    )
    events: list[AnswerEvent] = []
    for pk, is_correct, submitted_at in rows:
        events.append(AnswerEvent(pk, is_correct, submitted_at))
        if pk == answer.pk:
            break
    interaction = QuestionInteraction.objects.filter(
        attempt_id=attempt_id, question_id=answer.question_id
    ).first()
    contextual_triggers: list[SupervisorTrigger] = []
    if interaction is not None:
        change_limit = int(getattr(settings, "CHALLENGE_HESITATION_ANSWER_CHANGES", 3))
        long_limit = int(getattr(settings, "CHALLENGE_LONG_RESPONSE_SECONDS", 45))
        elapsed = (answer.submitted_at - interaction.displayed_at).total_seconds()
        if interaction.answer_changes >= change_limit:
            contextual_triggers.append(SupervisorTrigger.REPEATED_ANSWER_CHANGES)
    timeout_limit = int(getattr(settings, "CHALLENGE_SUPERVISOR_MULTIPLE_TIMEOUTS", 2))
    if QuestionInteraction.objects.filter(attempt_id=attempt_id, timed_out=True).count() >= timeout_limit:
        contextual_triggers.append(SupervisorTrigger.MULTIPLE_TIMEOUTS)
    if interaction is not None and elapsed >= long_limit:
        contextual_triggers.append(SupervisorTrigger.LONG_RESPONSE)
    return evaluate_trigger(
        attempt_id,
        events,
        created=created,
        attempt_completed=status == QuizAttempt.Status.COMPLETED,
        prior_interventions=prior_interventions,
        contextual_triggers=contextual_triggers,
    )
