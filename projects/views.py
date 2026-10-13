"""Vues de l'API des projets."""

import logging
import json

from django.conf import settings
from django.http import Http404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import SimpleRateThrottle

from .models import Project, ProjectAnalysis
from .ai.app_overview import APP_OVERVIEW
from .ai.client import call_chatbot_llm
from .ai.exceptions import LLMError
from .ai.prompts import CHATBOT_SYSTEM_PROMPT
from .ai.retrieval import retrieve_corpus, load_faq_corpus, build_user_analysis_corpus
from .ai.sanitizer import sanitize_project_text
from .permissions import IsProjectOwner
from .serializers import PublicProjectSerializer, ProjectSerializer
from .services.analysis import analyze_project
from users.permissions import IsApprovedUser


PAGE_SIZE = 10
MAX_CHATBOT_QUESTION_CHARS = 1000
MAX_CHATBOT_ANSWER_CHARS = 4000
CHATBOT_NO_INFORMATION = "Je n'ai pas l'information demandée."
CHATBOT_GENERIC_ERROR = "Le chatbot est momentanément indisponible."
logger = logging.getLogger(__name__)


class ProjectAnalysisThrottle(SimpleRateThrottle):
    """Limite le nombre d'analyses par utilisateur et par heure."""

    scope = "project-analysis"

    def get_cache_key(self, request, view):
        """Construit une clé de cache dédiée à l'utilisateur."""
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }

    def get_rate(self):
        """Retourne la limite configurée pour les analyses de projets."""
        return getattr(settings, "PROJECT_ANALYSIS_THROTTLE_RATE", "10/hour")


class ProjectChatbotThrottle(SimpleRateThrottle):
    """Limite les questions adressées au chatbot par utilisateur."""

    scope = "project-chatbot"

    def get_cache_key(self, request, view):
        """Construit une clé de cache dédiée à l'utilisateur."""
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }

    def get_rate(self):
        """Retourne la limite configurée pour le chatbot."""
        return getattr(settings, "PROJECT_CHATBOT_THROTTLE_RATE")


class ProjectListCreateView(generics.ListCreateAPIView):
    """Liste les projets du porteur ou crée un projet."""

    serializer_class = ProjectSerializer
    permission_classes = (IsProjectOwner,)

    def get_queryset(self):
        """Retourne uniquement les projets du porteur connecté."""
        queryset = Project.objects.filter(owner=self.request.user)
        requested_status = self.request.query_params.get("status")
        if requested_status is not None:
            valid_statuses = {choice.value for choice in Project.Status}
            if requested_status not in valid_statuses:
                raise ValidationError({"status": "Statut de projet inconnu."})
            queryset = queryset.filter(status=requested_status)
        return queryset

    def perform_create(self, serializer) -> None:
        """Associe le projet au porteur authentifié."""
        serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        """Crée un projet et journalise uniquement les champs invalides."""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "Création de projet refusée: champs invalides=%s",
                sorted(serializer.errors.keys()),
            )
            raise ValidationError(serializer.errors)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Consulte, modifie partiellement ou supprime un projet personnel."""

    serializer_class = ProjectSerializer
    permission_classes = (IsProjectOwner,)
    http_method_names = ("get", "patch", "delete", "head", "options")

    def get_queryset(self):
        """Limite chaque opération aux projets du porteur connecté."""
        return Project.objects.filter(owner=self.request.user)


class ProjectAnalyzeView(generics.GenericAPIView):
    """Lance une analyse IA sur un projet appartenant au porteur."""

    permission_classes = (IsProjectOwner,)
    throttle_classes = (ProjectAnalysisThrottle,)

    def post(self, request, pk: int):
        """Analyse le projet et retourne le résultat ou une erreur générique."""
        logger.info(
            "Requête d'analyse reçue: champs_body=%s",
            sorted(request.data.keys()),
        )
        project = Project.objects.filter(
            pk=pk,
            owner=request.user,
        ).first()
        if project is None:
            logger.warning("Analyse refusée: projet introuvable ou propriétaire différent.")
            raise Http404
        if project.status in (Project.Status.PUBLISHED, Project.Status.DECLINED):
            logger.warning(
                "Analyse refusée: état du projet non analysable=%s",
                project.status,
            )
            return Response(
                {
                    "error": "Ce projet ne peut pas être analysé dans son état actuel.",
                    "code": "project_state_invalid",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = analyze_project(project)
        return Response(payload, status=status.HTTP_200_OK)


class ProjectChatbotView(generics.GenericAPIView):
    """Répond aux questions du porteur à partir de ses sources autorisées."""

    permission_classes = (IsProjectOwner,)
    throttle_classes = (ProjectChatbotThrottle,)

    def post(self, request):
        """Valide la question, récupère les sources et répond au porteur."""
        question = request.data.get("question")
        if not isinstance(question, str) or not question.strip():
            return Response(
                {"detail": "La question ne peut pas être vide."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(question) > MAX_CHATBOT_QUESTION_CHARS:
            return Response(
                {"detail": "La question est trop longue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sanitized_question = sanitize_project_text(
            question,
            MAX_CHATBOT_QUESTION_CHARS,
        )
        corpus = load_faq_corpus() + build_user_analysis_corpus(request.user)
        blocks = retrieve_corpus(corpus, sanitized_question)
        context = (
            json.dumps(blocks, ensure_ascii=False)
            if blocks
            else APP_OVERVIEW
        )
        user_text = (
            f"<contexte>\n{context}\n</contexte>\n"
            f"<question>\n{sanitized_question}\n</question>"
        )
        simulated = getattr(settings, "CHATBOT_LLM_PROVIDER", "mock") == "mock"
        try:
            answer = call_chatbot_llm(CHATBOT_SYSTEM_PROMPT, user_text)
            if not isinstance(answer, str) or not answer.strip():
                raise LLMError("Réponse chatbot invalide.")
            answer = answer.strip()
            if len(answer) > MAX_CHATBOT_ANSWER_CHARS:
                raise LLMError("Réponse chatbot trop longue.")
        except LLMError as error:
            logger.warning(
                "Réponse chatbot indisponible: type=%s",
                type(error).__name__,
            )
            return Response(
                {
                    "answer": None,
                    "sources": [block["id"] for block in blocks],
                    "simulated": simulated,
                    "error": CHATBOT_GENERIC_ERROR,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "answer": answer,
                "sources": [block["id"] for block in blocks],
                "simulated": simulated,
            },
            status=status.HTTP_200_OK,
        )


class ProjectDecisionView(generics.GenericAPIView):
    """Applique la décision de publication ou de refus du propriétaire."""

    permission_classes = (IsProjectOwner,)

    def post(self, request, pk: int, decision: str):
        """Publie ou refuse un projet analysé avec succès."""
        project = Project.objects.filter(pk=pk, owner=request.user).first()
        if project is None:
            from django.http import Http404

            raise Http404
        if project.status != Project.Status.ANALYZED:
            return Response(
                {"detail": "Le projet doit être analysé avant cette décision."},
                status=status.HTTP_409_CONFLICT,
            )
        if not project.analyses.filter(result__isnull=False).exists():
            return Response(
                {"detail": "Une analyse réussie est requise."},
                status=status.HTTP_409_CONFLICT,
            )
        project.status = (
            Project.Status.PUBLISHED
            if decision == "publish"
            else Project.Status.DECLINED
        )
        project.save(update_fields=("status", "updated_at"))
        return Response({"status": project.status}, status=status.HTTP_200_OK)


class PublishedProjectListView(generics.ListAPIView):
    """Liste paginée des projets publiés et de leur synthèse d'analyse."""

    serializer_class = PublicProjectSerializer
    permission_classes = (IsApprovedUser,)
    pagination_class = type(
        "PublishedProjectPagination",
        (PageNumberPagination,),
        {"page_size": PAGE_SIZE},
    )

    def get_queryset(self):
        """Retourne uniquement les projets publiés avec leurs analyses."""
        return Project.objects.filter(status=Project.Status.PUBLISHED).prefetch_related(
            "analyses"
        )
