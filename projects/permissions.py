"""Permissions de l'application projects."""

from rest_framework.permissions import BasePermission

from users.models import User


class IsProjectOwner(BasePermission):
    """Autorise uniquement les porteurs de projet authentifiés."""

    message = "Accès réservé aux porteurs de projet authentifiés."

    def has_permission(self, request, view) -> bool:
        """Vérifie l'authentification et le rôle du compte."""
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.Role.PROJECT_OWNER
        )
