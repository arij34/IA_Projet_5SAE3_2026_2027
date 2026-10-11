"""Permissions spécifiques aux utilisateurs du module users."""

from rest_framework.permissions import BasePermission

from .models import User


class IsApprovedUser(BasePermission):
    """Autorise uniquement les utilisateurs authentifiés et approuvés."""

    message = "Votre profil est en cours de vérification par un administrateur."

    def has_permission(self, request, view):
        """Vérifie l'authentification et le statut de modération."""
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.moderation_status == User.ModerationStatus.OK:
            return True
        if user.moderation_status == User.ModerationStatus.REJETE:
            self.message = "Votre profil a été refusé."
        return False


class IsAdminRole(BasePermission):
    """Autorise uniquement les administrateurs approuvés."""

    message = "Accès réservé aux administrateurs approuvés."

    def has_permission(self, request, view):
        """Vérifie le rôle ADMIN et le statut de modération."""
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.Role.ADMIN
            and user.moderation_status == User.ModerationStatus.OK
        )
