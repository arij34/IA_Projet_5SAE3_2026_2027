from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .models import ModerationLog, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "moderation_status", "is_staff")
    list_filter = UserAdmin.list_filter + ("role", "moderation_status")
    search_fields = ("username", "email", "title")

    fieldsets = UserAdmin.fieldsets + (
        ("Rôle et profil", {"fields": ("role", "title", "bio", "skills", "hourly_rate")}),
        ("Modération", {"fields": ("moderation_status", "moderation_checked_at")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Informations complémentaires", {"fields": ("email", "role")}),
    )

    def save_model(self, request, obj, form, change):
        """Valide automatiquement les administrateurs créés depuis Django."""
        if obj.role == User.Role.ADMIN:
            # Le rôle ADMIN suffit pour l'application, sans accorder l'accès à /admin/.
            obj.moderation_status = User.ModerationStatus.OK
            if obj.moderation_checked_at is None:
                obj.moderation_checked_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    """Affiche l'historique de modération sans autoriser sa modification."""

    list_display = ("user", "decision", "confidence", "error", "created_at")
    list_filter = ("decision", "created_at")
    search_fields = ("user__username", "user__email", "reason")
    readonly_fields = (
        "user",
        "decision",
        "reason",
        "confidence",
        "error",
        "created_at",
    )

    def has_add_permission(self, request):
        """Interdit la création manuelle d'un journal."""
        return False

    def has_change_permission(self, request, obj=None):
        """Interdit la modification d'un journal."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Interdit la suppression d'un journal."""
        return False