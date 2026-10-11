import logging

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

logger = logging.getLogger(__name__)
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
        """Crée le compte puis lance sa modération avant la réponse."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        try:
            moderate_user_profile(user)
        except Exception:
            logger.exception(
                "Erreur inattendue pendant la modération de l'inscription."
            )
        user.refresh_from_db()
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
        """Met à jour le profil et remodère les champs concernés si nécessaire."""
        user = self.get_object()
        moderated_fields = ("title", "bio", "skills")
        profile_changed = any(
            field in serializer.validated_data
            and serializer.validated_data[field] != getattr(user, field)
            for field in moderated_fields
        )
        serializer.save()
        if not profile_changed:
            return

        try:
            moderate_user_profile(user)
        except Exception:
            logger.exception(
                "Erreur inattendue pendant la modération du profil utilisateur."
            )
        user.refresh_from_db()


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
