"""Cycle métier déterministe des tentatives de quiz."""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from challenges.models import AnswerChoice, Question, Quiz, QuizAttempt, SubmittedAnswer
from challenges.services.supervisor_events import persist_eligible_supervisor_event


logger = logging.getLogger(__name__)


class AttemptConflict(APIException):
    """Action incompatible avec l'état actuel d'une tentative."""

    status_code = 409
    default_detail = "Cette action ne peut pas être effectuée dans l'état actuel."
    default_code = "attempt_conflict"


def validate_quiz_ready(quiz: Quiz) -> int:
    """Refuse les quiz publiables qui n'ont pas une réponse valide par question."""
    questions = list(quiz.questions.prefetch_related("choices"))
    if not questions:
        raise ValidationError({"quiz": "Ce quiz ne contient aucune question."})
    for question in questions:
        choices = list(question.choices.all())
        if len(choices) < 2 or sum(choice.is_correct for choice in choices) != 1:
            raise ValidationError(
                {"quiz": "Le quiz contient une question dont les choix sont invalides."}
            )
    return len(questions)


def create_or_resume_attempt(user, quiz: Quiz) -> tuple[QuizAttempt, bool]:
    """Retourne la tentative active existante ou en crée une seule."""
    active_filter = {
        "user": user,
        "quiz": quiz,
        "status": QuizAttempt.Status.IN_PROGRESS,
    }
    existing = QuizAttempt.objects.filter(**active_filter).first()
    if existing is not None:
        return existing, False

    total_questions = validate_quiz_ready(quiz)
    try:
        with transaction.atomic():
            existing = QuizAttempt.objects.select_for_update().filter(**active_filter).first()
            if existing is not None:
                return existing, False
            attempt = QuizAttempt.objects.create(
                user=user,
                quiz=quiz,
                total_questions=total_questions,
            )
            return attempt, True
    except IntegrityError:
        existing = QuizAttempt.objects.filter(**active_filter).first()
        if existing is not None:
            return existing, False
        raise


def submit_answer(
    attempt: QuizAttempt,
    question: Question,
    selected_choice: AnswerChoice,
) -> tuple[SubmittedAnswer, bool]:
    """Persist one answer, returning the original row for identical retries."""
    if question.quiz_id != attempt.quiz_id:
        raise ValidationError({"question_id": "Cette question n'appartient pas au quiz."})
    if selected_choice.question_id != question.pk:
        raise ValidationError({"choice_id": "Ce choix n'appartient pas à la question."})

    with transaction.atomic():
        locked_attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked_attempt.status != QuizAttempt.Status.IN_PROGRESS:
            raise AttemptConflict("Cette tentative est déjà terminée.")

        existing = SubmittedAnswer.objects.filter(
            attempt=locked_attempt,
            question=question,
        ).first()
        if existing is not None:
            if existing.selected_choice_id == selected_choice.pk:
                return existing, False
            raise AttemptConflict("Une réponse a déjà été enregistrée pour cette question.")

        answer = SubmittedAnswer.objects.create(
            attempt=locked_attempt,
            question=question,
            selected_choice=selected_choice,
            is_correct=selected_choice.is_correct,
        )
        # The supervisor is optional: a failure must never roll back the answer.
        try:
            with transaction.atomic():
                persist_eligible_supervisor_event(answer)
        except Exception:
            logger.exception(
                "Supervisor event persistence failed for answer %s; answer kept.",
                answer.pk,
            )
        return answer, True


def complete_attempt(attempt: QuizAttempt) -> QuizAttempt:
    """Complete a fully answered attempt and calculate its score on the server."""
    with transaction.atomic():
        locked_attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked_attempt.status == QuizAttempt.Status.COMPLETED:
            return locked_attempt

        answers = list(locked_attempt.answers.all())
        if len(answers) != locked_attempt.total_questions:
            raise AttemptConflict("Répondez à toutes les questions avant de terminer.")

        correct_answers = sum(answer.is_correct for answer in answers)
        locked_attempt.correct_answers = correct_answers
        locked_attempt.score_percent = round(
            correct_answers * 100 / locked_attempt.total_questions
        )
        locked_attempt.status = QuizAttempt.Status.COMPLETED
        locked_attempt.completed_at = timezone.now()
        locked_attempt.save(
            update_fields=(
                "correct_answers",
                "score_percent",
                "status",
                "completed_at",
            )
        )
        return locked_attempt