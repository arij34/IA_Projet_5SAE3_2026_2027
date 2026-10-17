"""Persist deterministic supervisor triggers within an answer transaction."""

from django.db import IntegrityError, connection, transaction

from challenges.models import QuizAttempt, SubmittedAnswer, SupervisorEvent
from challenges.services.supervisor_policy import (
    PriorIntervention,
    SupervisorTrigger,
    evaluate_answer_event,
)

_UNIQUE_CONSTRAINTS = {
    "challenge_supervisor_event_key_uniq",
    "challenge_supervisor_attempt_trigger_uniq",
    "challenge_supervisor_attempt_slot_uniq",
    "challenges_supervisorevent_source_answer_id_key",
}
_SQLITE_UNIQUE_COLUMNS = (
    ("event_key",),
    ("attempt_id", "trigger_type"),
    ("attempt_id", "slot"),
    ("source_answer_id",),
)


def _is_expected_unique_conflict(error: IntegrityError) -> bool:
    cause = error.__cause__
    constraint_name = getattr(getattr(cause, "diag", None), "constraint_name", None)
    if constraint_name is not None:
        return constraint_name in _UNIQUE_CONSTRAINTS

    message = str(cause or error).lower()
    if "unique constraint failed:" not in message:
        return False
    columns = message.split("unique constraint failed:", 1)[1]
    return any(
        all(column in columns for column in expected)
        for expected in _SQLITE_UNIQUE_COLUMNS
    )


def persist_eligible_supervisor_event(
    answer: SubmittedAnswer,
) -> SupervisorEvent | None:
    """Persist an eligible event, requiring the answer's surrounding transaction.

    Database uniqueness handles duplicate identities. The caller must already
    hold the attempt row lock where the database supports row-level locking.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("Supervisor events must share the answer transaction.")

    attempt = QuizAttempt.objects.select_for_update().get(pk=answer.attempt_id)
    if attempt.status != QuizAttempt.Status.IN_PROGRESS:
        return None

    prior_events = list(
        SupervisorEvent.objects.select_for_update()
        .filter(attempt_id=attempt.pk)
        .order_by("slot")
    )
    prior_interventions = [
        PriorIntervention(
            trigger=SupervisorTrigger(event.trigger_type),
            created_at=event.created_at,
        )
        for event in prior_events
    ]
    decision = evaluate_answer_event(
        answer,
        created=True,
        prior_interventions=prior_interventions,
    )
    if decision.trigger is None or decision.event_key is None:
        return None

    used_slots = {event.slot for event in prior_events}
    slot = next((candidate for candidate in (1, 2) if candidate not in used_slots), None)
    if slot is None:
        return None

    try:
        with transaction.atomic():
            return SupervisorEvent.objects.create(
                attempt=attempt,
                source_answer=answer,
                trigger_type=decision.trigger.value,
                event_key=decision.event_key,
                slot=slot,
            )
    except IntegrityError as error:
        if not _is_expected_unique_conflict(error):
            raise

        duplicate_exists = (
            SupervisorEvent.objects.filter(event_key=decision.event_key).exists()
            or SupervisorEvent.objects.filter(
                attempt_id=attempt.pk,
                trigger_type=decision.trigger.value,
            ).exists()
            or SupervisorEvent.objects.filter(
                attempt_id=attempt.pk,
                slot=slot,
            ).exists()
            or SupervisorEvent.objects.filter(source_answer_id=answer.pk).exists()
        )
        if duplicate_exists:
            return None
        raise
