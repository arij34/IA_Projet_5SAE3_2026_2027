"""Modèles propres au module matching.

Aucun modèle des applications users, projects ou challenges n'est redéfini :
seules des clés étrangères vers ces modèles existants sont utilisées.
"""

from django.conf import settings
from django.db import models

from projects.models import Project

from .constants import ALGORITHM_VERSION


class MatchScore(models.Model):
    """Score de compatibilité calculé entre un projet et un freelance."""

    class Mode(models.TextChoices):
        """Origine du score final."""

        HYBRID = "HYBRID", "Déterministe + sémantique"
        DETERMINISTIC = "DETERMINISTIC", "Déterministe seul"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="match_scores",
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_scores",
    )
    speciality = models.CharField(
        "spécialité évaluée",
        max_length=120,
        blank=True,
        help_text="Vide lorsque le score agrège toutes les spécialités.",
    )
    total_score = models.FloatField("score global sur 100")
    deterministic_score = models.FloatField("score déterministe sur 100")
    semantic_score = models.FloatField(
        "score sémantique sur 100",
        null=True,
        blank=True,
    )
    mode = models.CharField(
        max_length=14,
        choices=Mode.choices,
        default=Mode.DETERMINISTIC,
    )
    breakdown = models.JSONField("détail des sous-scores", default=dict)
    algorithm_version = models.CharField(max_length=30, default=ALGORITHM_VERSION)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Un score courant par projet, freelance et spécialité."""

        ordering = ("-total_score", "freelancer_id")
        constraints = [
            models.UniqueConstraint(
                fields=("project", "freelancer", "speciality"),
                name="matching_score_unique_per_speciality",
            ),
        ]
        indexes = [
            models.Index(fields=("project", "-total_score")),
            models.Index(fields=("freelancer", "-total_score")),
        ]

    def __str__(self) -> str:
        """Retourne un libellé lisible du score."""
        label = self.speciality or "global"
        return f"{self.project_id} / {self.freelancer_id} ({label}) : {self.total_score}"


class Recommendation(models.Model):
    """Invitation envoyée par un porteur de projet à un freelance recommandé."""

    class Status(models.TextChoices):
        """Cycle de vie d'une recommandation."""

        PROPOSED = "PROPOSED", "Proposée"
        ACCEPTED = "ACCEPTED", "Acceptée"
        DECLINED = "DECLINED", "Refusée"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="match_recommendations",
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_recommendations",
    )
    speciality = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PROPOSED,
    )
    score_snapshot = models.FloatField(
        "score au moment de la proposition",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Une seule recommandation active par projet et freelance."""

        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("project", "freelancer"),
                name="matching_recommendation_unique_pair",
            ),
        ]

    def __str__(self) -> str:
        """Retourne un libellé lisible de la recommandation."""
        return f"{self.project_id} -> {self.freelancer_id} ({self.status})"
