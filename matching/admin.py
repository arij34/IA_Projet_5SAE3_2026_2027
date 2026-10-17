"""Administration du module matching, en lecture seule."""

from django.contrib import admin

from .models import MatchScore, Recommendation


@admin.register(MatchScore)
class MatchScoreAdmin(admin.ModelAdmin):
    """Consultation des scores calculés."""

    list_display = ("project", "freelancer", "speciality", "total_score", "mode")
    list_filter = ("mode", "algorithm_version")
    readonly_fields = ("computed_at",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    """Consultation des recommandations envoyées."""

    list_display = ("project", "freelancer", "status", "created_at")
    list_filter = ("status",)
