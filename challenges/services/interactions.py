"""Suivi serveur des interactions par question et métriques de tentative.

Les horodatages sont ceux du serveur ; le client ne peut pas modifier la
correction ni le score. Les métriques décrivent l'interaction avec le quiz,
pas l'état psychologique de l'utilisateur.
"""

from datetime import timedelta
from time import sleep

from django.conf import settings
from django.db import OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from challenges.models import (
    AnswerChoice,
    Question,
    QuestionInteraction,
    QuizAttempt,
    SubmittedAnswer,
)
from challenges.services.attempts import AttemptConflict

TIMEOUT_TOLERANCE_SECONDS = 2


def question_time_limit() -> int:
    return int(getattr(settings, "CHALLENGE_QUESTION_TIME_LIMIT_SECONDS", 60))


def _setting(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def _lock_open_attempt(attempt: QuizAttempt) -> QuizAttempt:
    locked = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
    if locked.status != QuizAttempt.Status.IN_PROGRESS:
        raise AttemptConflict("Cette tentative est déjà terminée.")
    return locked


def _get_or_create(attempt: QuizAttempt, question: Question, now):
    interaction, _ = QuestionInteraction.objects.get_or_create(
        attempt=attempt, question=question, defaults={"displayed_at": now}
    )
    return interaction


def _record_event_once(attempt, question: Question, event: str, choice: AnswerChoice | None = None):
    """Apply one idempotent interaction event and return the interaction."""
    if question.quiz_id != attempt.quiz_id:
        raise ValidationError({"question_id": "Cette question n'appartient pas au quiz."})
    now = timezone.now()
    with transaction.atomic():
        locked = _lock_open_attempt(attempt)
        interaction = _get_or_create(locked, question, now)
        answered = SubmittedAnswer.objects.filter(attempt=locked, question=question).exists()
        if event == "view" or answered:
            return interaction
        if event == "select":
            if choice is None or choice.question_id != question.pk:
                raise ValidationError({"choice_id": "Ce choix n'appartient pas à la question."})
            if interaction.first_selected_at is None:
                interaction.first_selected_at = now
            elif interaction.last_selected_choice_id != choice.pk:
                interaction.answer_changes += 1
            interaction.last_selected_choice_id = choice.pk
            interaction.save()
        elif event == "timeout" and not interaction.timed_out:
            elapsed = (now - interaction.displayed_at).total_seconds()
            if elapsed + TIMEOUT_TOLERANCE_SECONDS >= question_time_limit():
                interaction.timed_out = True
                interaction.timed_out_at = now
                interaction.save()
        return interaction


def record_event(attempt, question: Question, event: str, choice: AnswerChoice | None = None):
    """Record idempotently, retrying transient SQLite writer-lock conflicts."""
    for retry in range(5):
        try:
            return _record_event_once(attempt, question, event, choice)
        except OperationalError as error:
            if "locked" not in str(error).lower() or retry == 4:
                raise
            sleep(0.05 * (2 ** retry))


def compute_metrics(attempt: QuizAttempt) -> dict:
    """Aggregate attempt metrics from persisted rows only."""
    first_delay = _setting("CHALLENGE_HESITATION_FIRST_SELECTION_SECONDS", 20)
    change_limit = _setting("CHALLENGE_HESITATION_ANSWER_CHANGES", 3)
    long_limit = _setting("CHALLENGE_LONG_RESPONSE_SECONDS", 45)

    answers = {a.question_id: a for a in attempt.answers.all()}
    interactions = list(attempt.interactions.all())
    by_question = {i.question_id: i for i in interactions}

    response_times = []
    delayed = long_responses = many_changes = 0
    for question_id, answer in answers.items():
        interaction = by_question.get(question_id)
        if interaction is None:
            continue
        elapsed = max((answer.submitted_at - interaction.displayed_at).total_seconds(), 0)
        response_times.append(elapsed)
        if elapsed >= long_limit:
            long_responses += 1
    for interaction in interactions:
        if interaction.first_selected_at is not None:
            delay = (interaction.first_selected_at - interaction.displayed_at).total_seconds()
            if delay >= first_delay:
                delayed += 1
        if interaction.answer_changes >= change_limit:
            many_changes += 1

    submitted = len(answers)
    correct = sum(a.is_correct for a in answers.values())
    timeouts = sum(i.timed_out for i in interactions)
    total_answer_changes = sum(i.answer_changes for i in interactions)
    return {
        "total_questions": attempt.total_questions,
        "submitted_answers": submitted,
        "correct_answers": correct,
        "incorrect_answers": submitted - correct,
        "answer_changes": total_answer_changes,
        "total_answer_changes": total_answer_changes,
        "timeout_count": timeouts,
        "unanswered_questions": attempt.total_questions - submitted,
        "average_response_seconds": (
            round(sum(response_times) / len(response_times), 1) if response_times else None
        ),
        "accuracy_percent": round(correct * 100 / submitted) if submitted else None,
        "hesitation": {
            "delayed_first_selection": delayed,
            "many_answer_changes": many_changes,
            "long_response": long_responses,
        },
        "hesitation_events": delayed + many_changes + long_responses,
        "time_limit_seconds": question_time_limit(),
    }
