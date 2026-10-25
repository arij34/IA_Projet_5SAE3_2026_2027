"""Vues de lecture du catalogue des challenges."""

import logging

from django.conf import settings
from django.db import DatabaseError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from users.permissions import IsApprovedUser, IsFreelancerRole

from .models import ChallengeCategory, Quiz, QuizAttempt, SupervisorEvent
from .serializers import (
    QuizAttemptCompletionSerializer,
    QuizAttemptDetailSerializer,
    QuizAttemptResultSerializer,
    ChallengeCategorySerializer,
    GenerateQuizSerializer,
    PublicQuizDetailSerializer,
    PublicQuizListSerializer,
    StartAttemptSerializer,
    SubmitAnswerSerializer,
    SubmittedAnswerReceiptSerializer,
)
from .services.interactions import compute_metrics, record_event
from .services.generation import QuizGenerationError, generate_quiz
from .services.attempts import (
    AttemptConflict,
    complete_attempt,
    create_or_resume_attempt,
    submit_answer,
)
from .services.supervisor_messages import generate_supervisor_message
from .services.supervisor_delivery import (
    create_supervisor_connection_ticket,
    publish_attempt_completed,
    publish_supervisor_event,
)

CHALLENGE_PERMISSION_CLASSES = (IsApprovedUser, IsFreelancerRole)

logger = logging.getLogger(__name__)


class SupervisorUnavailable(APIException):
    status_code = 503
    default_detail = "Le superviseur IA est temporairement indisponible."
    default_code = "supervisor_unavailable"


class ChallengeCategoryListView(generics.ListAPIView):
    """Liste les catégories actives pour un utilisateur approuvé."""

    serializer_class = ChallengeCategorySerializer
    permission_classes = CHALLENGE_PERMISSION_CLASSES
    queryset = ChallengeCategory.objects.filter(is_active=True)


class PublishedQuizListView(generics.ListAPIView):
    """Liste les quiz publiés, éventuellement filtrés par catégorie/difficulté."""

    serializer_class = PublicQuizListSerializer
    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def get_queryset(self):
        queryset = (
            Quiz.objects.filter(
                status=Quiz.Status.PUBLISHED,
                category__is_active=True,
            )
            .select_related("category")
            .annotate(question_count=Count("questions"))
        )
        category = self.request.query_params.get("category")
        difficulty = self.request.query_params.get("difficulty")
        valid_difficulties = {value for value, _ in Quiz.Difficulty.choices}
        if difficulty and difficulty not in valid_difficulties:
            raise ValidationError({"difficulty": "Niveau de difficulté inconnu."})
        if category:
            queryset = queryset.filter(category__slug=category)
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        return queryset


class PublishedQuizDetailView(generics.RetrieveAPIView):
    """Retourne un quiz publié sans correction ni explication."""

    serializer_class = PublicQuizDetailSerializer
    permission_classes = CHALLENGE_PERMISSION_CLASSES
    queryset = (
        Quiz.objects.filter(
            status=Quiz.Status.PUBLISHED,
            category__is_active=True,
        )
        .select_related("category")
        .prefetch_related("questions__choices")
        .annotate(question_count=Count("questions"))
    )


class QuizGenerationThrottle(SimpleRateThrottle):
    """Limit paid LLM generations per freelancer."""

    scope = "challenge_generation"

    def get_rate(self):
        return getattr(settings, "CHALLENGE_GENERATION_THROTTLE_RATE", "5/hour")

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class GenerateQuizView(APIView):
    """Generate and publish an AI quiz; the API key never leaves the server."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES
    throttle_classes = (QuizGenerationThrottle,)

    def post(self, request):
        serializer = GenerateQuizSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quiz = generate_quiz(
                request.user,
                serializer.validated_data["category"],
                serializer.validated_data["difficulty"],
            )
        except QuizGenerationError as error:
            return Response({"detail": str(error)}, status=error.status_code)
        quiz.question_count = quiz.questions.count()
        return Response(
            PublicQuizDetailSerializer(quiz).data,
            status=status.HTTP_201_CREATED,
        )


class QuizAttemptCreateView(APIView):
    """Create or resume a freelancer's active attempt for a published quiz."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def post(self, request):
        serializer = StartAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt, created = create_or_resume_attempt(
            request.user,
            serializer.validated_data["quiz"],
        )
        return Response(
            QuizAttemptDetailSerializer(attempt).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


def get_owned_attempt(user, attempt_id: int) -> QuizAttempt:
    """Return only an attempt belonging to the authenticated freelancer."""
    return get_object_or_404(
        QuizAttempt.objects.select_related("quiz__category").filter(user=user),
        pk=attempt_id,
    )


class QuizAttemptDetailView(APIView):
    """Retrieve resumable attempt state without its answer key."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def get(self, request, pk: int):
        attempt = get_owned_attempt(request.user, pk)
        return Response(QuizAttemptDetailSerializer(attempt).data)


class SupervisorConnectionTicketThrottle(SimpleRateThrottle):
    """Limit short-lived supervisor socket credential issuance."""

    scope = "challenge_supervisor_ticket"

    def get_rate(self):
        return "60/hour"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class SupervisorConnectionTicketView(APIView):
    """Issue a one-time ticket to the owner of an active quiz attempt."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES
    throttle_classes = (SupervisorConnectionTicketThrottle,)

    def post(self, request, pk: int):
        attempt = get_owned_attempt(request.user, pk)
        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            raise AttemptConflict("La tentative est déjà terminée.")
        try:
            ticket, expires_at = create_supervisor_connection_ticket(
                request.user,
                attempt,
            )
        except DatabaseError:
            logger.exception("Supervisor ticket could not be issued.")
            raise SupervisorUnavailable()
        return Response(
            {"ticket": ticket, "expires_at": expires_at},
            status=status.HTTP_201_CREATED,
        )


class QuizAttemptAnswerView(APIView):
    """Submit one answer without disclosing its correctness."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def post(self, request, pk: int):
        attempt = get_owned_attempt(request.user, pk)
        serializer = SubmitAnswerSerializer(
            data=request.data,
            context={"attempt": attempt},
        )
        serializer.is_valid(raise_exception=True)
        answer, created = submit_answer(
            attempt,
            serializer.validated_data["question"],
            serializer.validated_data["selected_choice"],
        )
        if created:
            # Optional supervisor: the saved answer must be returned regardless.
            try:
                event = SupervisorEvent.objects.filter(
                    source_answer_id=answer.pk
                ).first()
                if event is not None:
                    generated_event = generate_supervisor_message(event)
                    if generated_event.generation_status in (
                        SupervisorEvent.GenerationStatus.GENERATED,
                        SupervisorEvent.GenerationStatus.FALLBACK,
                    ):
                        publish_supervisor_event(generated_event.pk)
            except Exception:
                logger.exception(
                    "Supervisor processing failed for answer %s; answer kept.",
                    answer.pk,
                )
        payload = SubmittedAnswerReceiptSerializer(answer).data
        payload["answered_count"] = attempt.answers.count()
        payload["total_questions"] = attempt.total_questions
        payload["already_submitted"] = not created
        return Response(
            payload,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class QuizAttemptInteractionView(APIView):
    """Record idempotent question interaction events (view, select, timeout)."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def post(self, request, pk: int):
        attempt = get_owned_attempt(request.user, pk)
        event = request.data.get("event")
        if event not in ("view", "select", "timeout"):
            raise ValidationError({"event": "Événement invalide."})
        question = get_object_or_404(
            attempt.quiz.questions, pk=_int_or_400(request.data.get("question_id"))
        )
        choice = None
        if event == "select":
            choice = get_object_or_404(
                question.choices, pk=_int_or_400(request.data.get("choice_id"))
            )
        interaction = record_event(attempt, question, event, choice)
        metrics = compute_metrics(attempt)
        metrics["question_elapsed_seconds"] = max(
            0, int((timezone.now() - interaction.displayed_at).total_seconds())
        )
        return Response(metrics)


class QuizAttemptMetricsView(APIView):
    """Return metrics computed from persisted attempt data only."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def get(self, request, pk: int):
        return Response(compute_metrics(get_owned_attempt(request.user, pk)))


def _int_or_400(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError({"detail": "Identifiant invalide."})
    return value


class QuizAttemptCompleteView(APIView):
    """Complete a fully answered attempt using deterministic server scoring."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def post(self, request, pk: int):
        attempt = get_owned_attempt(request.user, pk)
        completed_attempt = complete_attempt(attempt)
        publish_attempt_completed(completed_attempt.pk)
        return Response(QuizAttemptCompletionSerializer(completed_attempt).data)


class QuizAttemptResultView(APIView):
    """Return answer keys and explanations only after the owner completes."""

    permission_classes = CHALLENGE_PERMISSION_CLASSES

    def get(self, request, pk: int):
        attempt = get_owned_attempt(request.user, pk)
        if attempt.status != QuizAttempt.Status.COMPLETED:
            raise AttemptConflict("Les résultats sont disponibles après la fin du quiz.")
        return Response(QuizAttemptResultSerializer(attempt).data)
