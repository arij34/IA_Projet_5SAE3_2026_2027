"""Administration de l'application projects."""

from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Affiche les projets dans l'administration Django."""

    list_display = ("name", "owner", "status", "deadline", "estimated_amount")
    list_filter = ("status",)
    search_fields = ("name", "owner__username")
