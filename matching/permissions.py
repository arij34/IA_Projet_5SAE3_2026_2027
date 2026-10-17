"""Permissions du module matching.

Les permissions existantes des modules users et projects sont réutilisées :
aucune n'est redéfinie ni modifiée.
"""

from rest_framework.permissions import BasePermission

from projects.permissions import IsProjectOwner
from users.permissions import IsApprovedUser, IsFreelancerRole


class IsApprovedProjectOwner(BasePermission):
    """Porteur de projet authentifié et validé par la modération."""

    message = "Accès réservé aux porteurs de projet validés."

    def has_permission(self, request, view) -> bool:
        """Combine le contrôle de rôle et le contrôle de modération."""
        owner = IsProjectOwner()
        approved = IsApprovedUser()
        if not owner.has_permission(request, view):
            self.message = owner.message
            return False
        if not approved.has_permission(request, view):
            self.message = approved.message
            return False
        return True


class IsApprovedFreelancer(BasePermission):
    """Freelance authentifié et validé par la modération."""

    message = "Accès réservé aux freelances validés."

    def has_permission(self, request, view) -> bool:
        """Combine le contrôle de rôle et le contrôle de modération."""
        freelancer = IsFreelancerRole()
        approved = IsApprovedUser()
        if not freelancer.has_permission(request, view):
            self.message = freelancer.message
            return False
        if not approved.has_permission(request, view):
            self.message = approved.message
            return False
        return True
