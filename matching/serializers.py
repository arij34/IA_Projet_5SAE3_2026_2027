"""Sérialiseurs du module matching.

Les réponses exposent une liste blanche de champs : ni e-mail, ni CV, ni
statut de modération, ni donnée privée des autres modules.
"""

from rest_framework import serializers

from .models import MatchScore, Recommendation


class SubscoreSerializer(serializers.Serializer):
    """Détail d'un sous-score, y compris lorsqu'il est neutralisé."""

    available = serializers.BooleanField()
    score = serializers.FloatField(allow_null=True)
    detail = serializers.CharField(allow_blank=True, required=False)


class FreelancerMatchSerializer(serializers.Serializer):
    """Freelance recommandé pour un projet, avec son score explicable."""

    freelancer_id = serializers.IntegerField()
    username = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    hourly_rate = serializers.FloatField(allow_null=True)
    skills = serializers.ListField(child=serializers.CharField())
    speciality = serializers.CharField(allow_blank=True)
    required_level = serializers.CharField(allow_null=True)
    total_score = serializers.FloatField()
    deterministic_score = serializers.FloatField()
    semantic_score = serializers.FloatField(allow_null=True)
    semantic_available = serializers.BooleanField()
    semantic_justification = serializers.CharField(allow_null=True, required=False)
    semantic_concepts = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    mode = serializers.CharField()
    semantic_weight = serializers.FloatField()
    subscores = serializers.DictField()
    applied_weights = serializers.DictField()
    skipped_criteria = serializers.ListField(child=serializers.CharField())
    speciality_scores = serializers.ListField(child=serializers.DictField())
    explanations = serializers.ListField(child=serializers.CharField())
    algorithm_version = serializers.CharField()


class RecommendedProjectSerializer(serializers.Serializer):
    """Projet publié recommandé à un freelance."""

    project_id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    deadline = serializers.DateField()
    estimated_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    budget_min = serializers.FloatField(allow_null=True, required=False)
    budget_max = serializers.FloatField(allow_null=True, required=False)
    duree_semaines = serializers.IntegerField(allow_null=True, required=False)
    required_specialities = serializers.ListField(child=serializers.DictField())
    match = FreelancerMatchSerializer()


class MatchScoreSerializer(serializers.ModelSerializer):
    """Score persisté, exposé sans donnée personnelle superflue."""

    freelancer_id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(source="freelancer.username", read_only=True)
    title = serializers.CharField(source="freelancer.title", read_only=True)

    class Meta:
        """Liste blanche des champs exposés du score."""

        model = MatchScore
        fields = (
            "id",
            "project_id",
            "freelancer_id",
            "username",
            "title",
            "speciality",
            "total_score",
            "deterministic_score",
            "semantic_score",
            "mode",
            "breakdown",
            "algorithm_version",
            "computed_at",
        )
        read_only_fields = fields


class RecommendationSerializer(serializers.ModelSerializer):
    """Recommandation échangée entre un porteur et un freelance."""

    project_name = serializers.CharField(source="project.name", read_only=True)
    freelancer_username = serializers.CharField(
        source="freelancer.username", read_only=True
    )

    class Meta:
        """Liste blanche des champs exposés d'une recommandation."""

        model = Recommendation
        fields = (
            "id",
            "project",
            "project_name",
            "freelancer",
            "freelancer_username",
            "speciality",
            "status",
            "score_snapshot",
            "created_at",
            "responded_at",
        )
        read_only_fields = fields


class RecommendationCreateSerializer(serializers.Serializer):
    """Demande de création d'une recommandation par le porteur de projet."""

    freelancer_id = serializers.IntegerField()
    speciality = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )


class RecommendationResponseSerializer(serializers.Serializer):
    """Réponse d'un freelance à une recommandation reçue."""

    decision = serializers.ChoiceField(choices=("accept", "decline"))


class TeamMemberSerializer(serializers.Serializer):
    """Membre retenu dans une proposition d'équipe."""

    speciality = serializers.CharField(allow_null=True)
    required_level = serializers.CharField(allow_null=True)
    freelancer_id = serializers.IntegerField()
    username = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    hourly_rate = serializers.FloatField(allow_null=True)
    score = serializers.FloatField()
    skill_score = serializers.FloatField(allow_null=True)
    skill_covered = serializers.BooleanField()
    matched_skills = serializers.ListField(child=serializers.CharField())
    missing_skills = serializers.ListField(child=serializers.CharField())
    estimated_cost = serializers.FloatField(allow_null=True)
    justification = serializers.CharField(allow_blank=True)


class TeamSerializer(serializers.Serializer):
    """Proposition d'équipe, avec dotation et couverture distinguées."""

    fully_staffed = serializers.BooleanField()
    fully_covered = serializers.BooleanField()
    required_positions = serializers.IntegerField()
    assigned_positions = serializers.IntegerField()
    skill_covered_positions = serializers.IntegerField()
    members = TeamMemberSerializer(many=True)
    uncovered = serializers.ListField(child=serializers.DictField())
    estimated_cost = serializers.FloatField(allow_null=True)
    estimated_cost_partial = serializers.BooleanField()
    budget_total = serializers.FloatField(allow_null=True)
    budget_source = serializers.CharField()
    over_budget = serializers.BooleanField()
    alerts = serializers.ListField(child=serializers.CharField())
    assumptions = serializers.DictField()
    algorithm_version = serializers.CharField()
