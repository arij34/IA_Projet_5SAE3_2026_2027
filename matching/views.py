"""Vues de l'API du module matching.

Toutes les règles d'accès sont vérifiées côté serveur : rôle, modération,
propriété du projet et statut de publication. L'identité de l'appelant
provient exclusivement du jeton d'authentification, jamais du corps de requête.
"""

import logging

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from projects.models import Project

from .models import MatchScore, Recommendation
from .permissions import IsApprovedFreelancer, IsApprovedProjectOwner
from .serializers import (
    FreelancerMatchSerializer,
    MatchScoreSerializer,
    RecommendationCreateSerializer,
    RecommendationResponseSerializer,
    RecommendationSerializer,
    RecommendedProjectSerializer,
    TeamSerializer,
)
from .services import engine
from .services.quiz_scoring import load_quiz_profile
from .services.team_builder import build_team
from .services import smart_matching

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
ANALYSIS_REQUIRED = (
    "Ce projet doit disposer d'une analyse IA réussie avant tout matching."
)


class MatchingPagination(PageNumberPagination):
    """Pagination commune aux listes du matching."""

    page_size = PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE


class MatchingRefreshThrottle(SimpleRateThrottle):
    """Limite les recalculs, qui peuvent déclencher des appels IA."""

    scope = "matching-refresh"

    def get_cache_key(self, request, view):
        """Construit une clé de cache dédiée à l'utilisateur."""
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}

    def get_rate(self):
        """Retourne la limite configurée pour les recalculs de matching."""
        return getattr(settings, "MATCHING_REFRESH_THROTTLE_RATE", "10/hour")


def _owned_project(request, pk: int) -> Project:
    """Retourne le projet du porteur connecté ou lève une erreur 404."""
    project = Project.objects.filter(pk=pk, owner=request.user).first()
    if project is None:
        raise Http404
    return project


def _analysis_or_error(project: Project):
    """Retourne l'analyse exploitable d'un projet ou une réponse d'erreur."""
    analysis = engine.latest_analysis_result(project)
    if analysis is None:
        return None, Response(
            {"detail": ANALYSIS_REQUIRED, "code": "analysis_required"},
            status=status.HTTP_409_CONFLICT,
        )
    return analysis, None


def _wants_semantic(request) -> bool:
    """Indique si l'appelant demande l'enrichissement sémantique par IA."""
    raw = str(request.query_params.get("semantic", "")).lower()
    if raw in ("1", "true", "oui", "yes"):
        return True
    if raw in ("0", "false", "non", "no", ""):
        return False
    raise ValidationError({"semantic": "Valeur booléenne attendue."})


def _limit(request, default: int = 50) -> int:
    """Valide le paramètre de limite de calcul."""
    raw = request.query_params.get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({"limit": "Entier attendu."}) from None
    if not 1 <= value <= 200:
        raise ValidationError({"limit": "Valeur comprise entre 1 et 200."})
    return value


class ProjectFreelancerMatchView(GenericAPIView):
    """Recommande les freelances adaptés à un projet du porteur connecté."""

    permission_classes = (IsApprovedProjectOwner,)
    serializer_class = FreelancerMatchSerializer
    pagination_class = MatchingPagination

    def get(self, request, pk: int):
        """Calcule et retourne le classement paginé des freelances."""
        project = _owned_project(request, pk)
        analysis, error = _analysis_or_error(project)
        if error is not None:
            return error

        results = engine.rank_freelancers(
            project,
            analysis,
            use_semantic=_wants_semantic(request),
            limit=_limit(request),
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(results, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SmartProjectMatchView(GenericAPIView):
    """Classement ponctuel depuis un brief libre, sans modifier le projet."""

    permission_classes = (IsApprovedProjectOwner,)
    serializer_class = FreelancerMatchSerializer

    def post(self, request, pk: int):
        project = _owned_project(request, pk)
        if not isinstance(request.data, dict):
            raise ValidationError({"description": "Objet JSON attendu."})
        description = request.data.get("description")
        if not isinstance(description, str) or not description.strip() or len(description) > 3000:
            raise ValidationError({"description": "Description requise (3000 caractères maximum)."})
        try:
            criteria = smart_matching.extract_criteria(description)
            analysis = smart_matching.criteria_as_analysis(criteria)
            criteria_available = True
        except Exception as error:
            logger.info("Extraction du matching intelligent indisponible: %s", type(error).__name__)
            analysis = engine.latest_analysis_result(project)
            criteria = None
            criteria_available = False
            if analysis is None:
                return Response(
                    {"detail": "Extraction IA indisponible et aucune analyse existante pour le repli.",
                     "code": "smart_matching_unavailable"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        results = engine.rank_freelancers(project, analysis, limit=50)
        if criteria_available:
            for item in results[:3]:
                item["smart_explanation"] = smart_matching.safe_explain(
                    description, criteria, item
                )
        serializer = self.get_serializer(results, many=True)
        return Response({"criteria": criteria, "criteria_available": criteria_available,
                         "results": serializer.data}, status=status.HTTP_200_OK)


class ProjectMatchScoreListView(GenericAPIView):
    """Retourne les scores déjà calculés et persistés pour un projet."""

    permission_classes = (IsApprovedProjectOwner,)
    serializer_class = MatchScoreSerializer
    pagination_class = MatchingPagination

    def get(self, request, pk: int):
        """Liste les scores enregistrés du projet, du meilleur au moins bon."""
        project = _owned_project(request, pk)
        queryset = (
            MatchScore.objects.filter(project=project)
            .select_related("freelancer")
            .order_by("-total_score", "freelancer_id")
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ProjectMatchRefreshView(GenericAPIView):
    """Recalcule et persiste les scores d'un projet du porteur connecté."""

    permission_classes = (IsApprovedProjectOwner,)
    throttle_classes = (MatchingRefreshThrottle,)
    serializer_class = FreelancerMatchSerializer

    def post(self, request, pk: int):
        """Relance le calcul puis enregistre les scores obtenus."""
        project = _owned_project(request, pk)
        analysis, error = _analysis_or_error(project)
        if error is not None:
            return error

        results = engine.rank_freelancers(
            project,
            analysis,
            use_semantic=_wants_semantic(request),
            limit=_limit(request),
        )
        stored = engine.persist_scores(project, results)
        degraded = [
            item for item in results if item["mode"] == "DETERMINISTIC"
        ]
        return Response(
            {
                "computed": len(results),
                "stored": stored,
                "semantic_unavailable": len(degraded) == len(results)
                and bool(results),
                "results": self.get_serializer(results, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class ProjectTeamView(GenericAPIView):
    """Propose une équipe couvrant les spécialités du projet."""

    permission_classes = (IsApprovedProjectOwner,)
    serializer_class = TeamSerializer

    def get(self, request, pk: int):
        """Construit une proposition d'équipe déterministe."""
        project = _owned_project(request, pk)
        analysis, error = _analysis_or_error(project)
        if error is not None:
            return error
        team = build_team(project, analysis)
        return Response(self.get_serializer(team).data, status=status.HTTP_200_OK)


class RecommendedProjectListView(GenericAPIView):
    """Recommande au freelance connecté les projets publiés adaptés."""

    permission_classes = (IsApprovedFreelancer,)
    serializer_class = RecommendedProjectSerializer
    pagination_class = MatchingPagination

    def get(self, request):
        """Classe les projets publiés selon le profil du freelance connecté."""
        quiz_profile = load_quiz_profile(request.user)
        results = engine.rank_projects_for_freelancer(
            request.user,
            quiz_profile,
            use_semantic=_wants_semantic(request),
            limit=_limit(request),
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(results, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ProjectRecommendationCreateView(GenericAPIView):
    """Permet au porteur d'inviter un freelance recommandé."""

    permission_classes = (IsApprovedProjectOwner,)
    serializer_class = RecommendationCreateSerializer

    def post(self, request, pk: int):
        """Crée une recommandation vers un freelance éligible."""
        project = _owned_project(request, pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        freelancer_id = serializer.validated_data["freelancer_id"]

        freelancer = engine.eligible_freelancers().filter(pk=freelancer_id).first()
        if freelancer is None:
            return Response(
                {"detail": "Freelance introuvable ou non validé."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        speciality = serializer.validated_data.get("speciality", "")
        score = (
            MatchScore.objects.filter(project=project, freelancer=freelancer)
            .order_by("-total_score")
            .first()
        )
        recommendation, created = Recommendation.objects.get_or_create(
            project=project,
            freelancer=freelancer,
            defaults={
                "speciality": speciality,
                "score_snapshot": score.total_score if score else None,
            },
        )
        return Response(
            RecommendationSerializer(recommendation).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MyRecommendationListView(GenericAPIView):
    """Liste les recommandations reçues par le freelance connecté."""

    permission_classes = (IsApprovedFreelancer,)
    serializer_class = RecommendationSerializer
    pagination_class = MatchingPagination

    def get(self, request):
        """Retourne uniquement les recommandations adressées à l'appelant."""
        queryset = (
            Recommendation.objects.filter(freelancer=request.user)
            .select_related("project", "freelancer")
            .order_by("-created_at")
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class RecommendationRespondView(GenericAPIView):
    """Permet au freelance destinataire d'accepter ou de refuser."""

    permission_classes = (IsApprovedFreelancer,)
    serializer_class = RecommendationResponseSerializer

    def post(self, request, pk: int):
        """Applique la décision du freelance sur sa propre recommandation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recommendation = Recommendation.objects.filter(
            pk=pk, freelancer=request.user
        ).first()
        if recommendation is None:
            raise Http404
        if recommendation.status != Recommendation.Status.PROPOSED:
            return Response(
                {"detail": "Cette recommandation a déjà reçu une réponse."},
                status=status.HTTP_409_CONFLICT,
            )

        recommendation.status = (
            Recommendation.Status.ACCEPTED
            if serializer.validated_data["decision"] == "accept"
            else Recommendation.Status.DECLINED
        )
        recommendation.responded_at = timezone.now()
        recommendation.save(update_fields=("status", "responded_at"))
        return Response(
            RecommendationSerializer(recommendation).data,
            status=status.HTTP_200_OK,
        )
