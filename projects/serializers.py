"""Sérialiseurs de l'API des projets."""

from django.utils import timezone
from rest_framework import serializers

from .models import MAX_DESCRIPTION_CHARS, MAX_NAME_CHARS, Project, ProjectAnalysis


class ProjectSerializer(serializers.ModelSerializer):
    """Valide et expose les projets du porteur authentifié."""

    class Meta:
        """Déclare les champs et les protections d'écriture du projet."""

        model = Project
        fields = (
            "id",
            "owner",
            "name",
            "description",
            "deadline",
            "estimated_amount",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "owner", "status", "created_at", "updated_at")
        extra_kwargs = {
            "name": {"max_length": MAX_NAME_CHARS},
            "description": {"max_length": MAX_DESCRIPTION_CHARS},
        }

    def validate_name(self, value: str) -> str:
        """Refuse un nom vide, y compris composé uniquement d'espaces."""
        if not value.strip():
            raise serializers.ValidationError("Le nom ne peut pas être vide.")
        return value

    def validate_deadline(self, value):
        """Exige une échéance strictement postérieure à la date du jour."""
        if value <= timezone.localdate():
            raise serializers.ValidationError(
                "La date limite doit être strictement dans le futur."
            )
        return value

    def validate_estimated_amount(self, value):
        """Refuse un montant nul ou négatif."""
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être strictement positif.")
        return value

    def update(self, instance: Project, validated_data: dict) -> Project:
        """Réinitialise le statut si un champ métier est modifié."""
        if instance.status == Project.Status.PUBLISHED and {
            "description",
            "deadline",
            "estimated_amount",
        }.intersection(validated_data):
            raise serializers.ValidationError(
                "Un projet publié ne peut plus modifier ses éléments métier."
            )
        tracked_fields = {"description", "deadline", "estimated_amount"}
        if tracked_fields.intersection(validated_data):
            validated_data["status"] = Project.Status.DRAFT
        return super().update(instance, validated_data)


class PublicAnalysisSerializer(serializers.ModelSerializer):
    """Expose uniquement la synthèse publique d'une analyse réussie."""

    class Meta:
        """Déclare la whitelist des champs d'analyse publiables."""

        model = ProjectAnalysis
        fields = (
            "budget_min",
            "budget_max",
            "nb_freelancers",
            "specialites",
            "duree_semaines",
            "complexite",
        )

    budget_min = serializers.JSONField(source="result.budget_min")
    budget_max = serializers.JSONField(source="result.budget_max")
    nb_freelancers = serializers.JSONField(source="result.nb_freelancers")
    specialites = serializers.JSONField(source="result.specialites")
    duree_semaines = serializers.JSONField(source="result.duree_semaines")
    complexite = serializers.JSONField(source="result.complexite")


class PublicProjectSerializer(serializers.ModelSerializer):
    """Expose la whitelist d'un projet publié sans données du propriétaire."""

    analysis = serializers.SerializerMethodField()

    class Meta:
        """Déclare les seuls champs visibles publiquement."""

        model = Project
        fields = (
            "id",
            "name",
            "description",
            "deadline",
            "estimated_amount",
            "analysis",
        )

    def get_analysis(self, obj: Project) -> dict | None:
        """Retourne la dernière analyse disposant d'un résultat."""
        analysis = next(
            (
                item
                for item in obj.analyses.all()
                if item.result is not None and not item.error
            ),
            None,
        )
        return PublicAnalysisSerializer(analysis).data if analysis else None
