"""Vues de l'API des projets."""

import logging

from django.conf import settings
from django.http import Http404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import SimpleRateThrottle

from .models import Project, ProjectAnalysis
from .permissions import IsProjectOwner
from .serializers import PublicProjectSerializer, ProjectSerializer
from .services.analysis import GENERIC_LLM_ERROR, INTERNAL_ERROR, analyze_project
from users.permissions import IsApprovedUser


PAGE_SIZE = 10
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
        if payload["error"] == GENERIC_LLM_ERROR:
            return Response(payload, status=status.HTTP_502_BAD_GATEWAY)
        if payload["error"] == INTERNAL_ERROR:
            return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(payload, status=status.HTTP_200_OK)


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
