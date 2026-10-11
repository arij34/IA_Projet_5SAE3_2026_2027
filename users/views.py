from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ModerationLog, User
from .permissions import IsAdminRole, IsApprovedUser
from .services.moderation import moderate_user_profile
from .serializers import (
    LoginSerializer,
    ModerationDetailSerializer,
    ModerationListSerializer,
    ProfileSerializer,
    RegisterSerializer,
)

MODERATION_STATUSES = frozenset(
    (
        User.ModerationStatus.PENDING,
        User.ModerationStatus.SUSPECT,
        User.ModerationStatus.REJETE,
    )
)


def _moderation_queryset():
    """Retourne le queryset commun des profils modérables."""
    latest_log = ModerationLog.objects.filter(user=OuterRef("pk")).order_by(
        "-created_at"
    )
    return (
        User.objects.filter(
            moderation_status__in=MODERATION_STATUSES,
        )
        .exclude(role=User.Role.ADMIN)
        .annotate(
            latest_reason=Subquery(latest_log.values("reason")[:1]),
        )
        .order_by("-moderation_checked_at", "-id")
    )


class RegisterView(CreateAPIView):
    """Expose l'inscription publique des utilisateurs."""

    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        """Crée le compte et le laisse en attente de vérification."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializer.to_representation(user), status=201)


class LoginView(CreateAPIView):
    """Expose la connexion publique par jeton d'authentification."""

    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        """Retourne les données de connexion avec le statut HTTP 200."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data)


class MeView(RetrieveUpdateAPIView):
    """Permet à l'utilisateur authentifié de consulter son propre profil."""

    serializer_class = ProfileSerializer
    permission_classes = (IsApprovedUser,)
    http_method_names = ("get", "patch", "head", "options")

    def get_object(self):
        """Retourne toujours l'utilisateur authentifié de la requête."""
        return self.request.user

    def perform_update(self, serializer):
        """Met à jour le profil sans lancer d'analyse automatique."""
        serializer.save()


class ModerationListView(APIView):
    """Liste les profils nécessitant une action administrative."""

    permission_classes = (IsAdminRole,)

    def get(self, request):
        """Retourne les profils modérables, éventuellement filtrés."""
        selected_status = request.query_params.get("status")
        if selected_status and selected_status not in MODERATION_STATUSES:
            return Response(
                {"detail": "Statut de modération invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = _moderation_queryset()
        if selected_status:
            queryset = queryset.filter(moderation_status=selected_status)
        serializer = ModerationListSerializer(queryset, many=True)
        return Response(serializer.data)


class ModerationDetailView(APIView):
    """Retourne le détail d'un profil modérable."""

    permission_classes = (IsAdminRole,)

    def get(self, request, pk):
        """Retourne un profil hors du périmètre administratif interdit."""
        user = _moderation_queryset().filter(pk=pk).first()
        if user is None:
            raise NotFound()
        return Response(ModerationDetailSerializer(user).data)

    def delete(self, request, pk):
        """Supprime un profil modérable."""
        user = _moderation_queryset().filter(pk=pk).first()
        if user is None:
            raise NotFound()
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModerationApproveView(APIView):
    """Valide manuellement un profil en attente ou suspect."""

    permission_classes = (IsAdminRole,)

    def post(self, request, pk):
        """Approuve un profil et consigne la décision administrative."""
        user = _moderation_queryset().filter(pk=pk).first()
        if user is None:
            raise NotFound()
        if user.moderation_status == User.ModerationStatus.REJETE:
            return Response(
                {"detail": "Un profil rejeté ne peut pas être approuvé."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            user.moderation_status = User.ModerationStatus.OK
            user.moderation_checked_at = timezone.now()
            user.save(update_fields=("moderation_status", "moderation_checked_at"))
            ModerationLog.objects.create(
                user=user,
                decision=User.ModerationStatus.OK,
                reason=f"Validé manuellement par {request.user.username}",
                confidence=None,
            )
        return Response(ModerationDetailSerializer(user).data)


class ModerationAnalyzeView(APIView):
    """Analyse un profil à la demande d'un administrateur."""

    permission_classes = (IsAdminRole,)

    def post(self, request, pk):
        """Lance une analyse sans modifier le statut du profil."""
        user = User.objects.filter(pk=pk).first()
        if user is None:
            raise NotFound()
        if user.role == User.Role.ADMIN:
            return Response(
                {"detail": "Un compte administrateur ne peut pas être analysé."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.moderation_status != User.ModerationStatus.PENDING:
            return Response(
                {
                    "detail": (
                        "Seuls les comptes en attente peuvent être analysés."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        log = moderate_user_profile(user)
        if log is None:
            return Response(
                {"detail": "Ce compte ne peut pas être analysé."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        confidence_percent = (
            None
            if log.confidence is None
            else max(0, min(100, int(round(log.confidence * 100))))
        )
        return Response(
            {
                "decision": log.decision,
                "reason": log.reason,
                "confidence_percent": confidence_percent,
                "analyzed_at": log.created_at,
                "error": log.error,
            }
        )
