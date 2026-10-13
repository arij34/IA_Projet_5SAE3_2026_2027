"""Modèle de projet de l'application projects."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from users.models import User


MAX_NAME_CHARS = 150
MAX_DESCRIPTION_CHARS = 3000


class Project(models.Model):
    """Projet créé et géré par un porteur de projet."""

    class Status(models.TextChoices):
        """Statuts disponibles pour un projet."""

        DRAFT = "DRAFT", "Brouillon"
        ANALYZED = "ANALYZED", "Analysé"
        PUBLISHED = "PUBLISHED", "Publié"
        DECLINED = "DECLINED", "Refusé"

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=MAX_NAME_CHARS)
    description = models.TextField(max_length=MAX_DESCRIPTION_CHARS)
    deadline = models.DateField()
    estimated_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Options d'affichage des projets."""

        ordering = ("-created_at",)

    def __str__(self) -> str:
        """Retourne le nom du projet."""
        return self.name


class ProjectAnalysis(models.Model):
    """Résultat historisé d'une analyse IA d'un projet."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="analyses",
    )
    result = models.JSONField(null=True, blank=True)
    simulated = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Options d'affichage des analyses."""

        ordering = ("-created_at",)
