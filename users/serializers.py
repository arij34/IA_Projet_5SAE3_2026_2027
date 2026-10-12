"""Sérialiseurs de l'API du module users."""

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .models import ModerationLog, User


class RegisterSerializer(serializers.ModelSerializer):
    """Valide et crée un utilisateur depuis une demande d'inscription."""

    password = serializers.CharField(write_only=True)

    class Meta:
        """Déclare les champs publics de l'inscription."""

        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "role",
            "title",
            "bio",
            "skills",
            "moderation_status",
        )
        read_only_fields = ("id", "moderation_status")
        extra_kwargs = {
            "role": {
                "choices": (
                    User.Role.FREELANCER,
                    User.Role.PROJECT_OWNER,
                ),
            },
        }

    def to_internal_value(self, data):
        """Ignore les champs protégés envoyés par le client."""
        sanitized_data = data.copy()
        for field in ("moderation_status", "moderation_checked_at", "is_staff"):
            sanitized_data.pop(field, None)
        return super().to_internal_value(sanitized_data)

    def validate_password(self, value):
        """Applique les validateurs de mot de passe configurés dans Django."""
        validate_password(value)
        return value

    def create(self, validated_data):
        """Crée l'utilisateur avec un mot de passe correctement haché."""
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class LoginUserSerializer(serializers.ModelSerializer):
    """Expose les informations publiques de l'utilisateur connecté."""

    class Meta:
        """Déclare les informations renvoyées après connexion."""

        model = User
        fields = ("id", "username", "email", "role", "moderation_status")


class LoginSerializer(serializers.Serializer):
    """Valide les identifiants et prépare la réponse de connexion."""

    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(read_only=True)
    user = LoginUserSerializer(read_only=True)

    def validate(self, attrs):
        """Authentifie l'utilisateur avec un message d'erreur générique."""
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("Identifiants invalides.")
        if user.moderation_status != User.ModerationStatus.OK:
            if user.moderation_status == User.ModerationStatus.REJETE:
                message = "Votre profil a été refusé."
            else:
                message = (
                    "Votre profil est en cours de vérification "
                    "par un administrateur."
                )
            raise PermissionDenied(
                detail={
                    "detail": message,
                    "moderation_status": user.moderation_status,
                }
            )
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        """Crée ou récupère le jeton de l'utilisateur authentifié."""
        from rest_framework.authtoken.models import Token

        token, _ = Token.objects.get_or_create(user=validated_data["user"])
        return {"token": token.key, "user": validated_data["user"]}


class ProfileSerializer(serializers.ModelSerializer):
    """Sérialise le profil de l'utilisateur actuellement authentifié."""

    class Meta:
        """Déclare les champs consultables et modifiables du profil."""

        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "title",
            "bio",
            "skills",
            "hourly_rate",
            "moderation_status",
            "moderation_checked_at",
            "has_cv",
        )
        read_only_fields = (
            "id",
            "username",
            "email",
            "role",
            "moderation_status",
            "moderation_checked_at",
        )

    has_cv = serializers.SerializerMethodField()

    def get_has_cv(self, obj: User) -> bool:
        """Indique uniquement si un CV est enregistré, sans exposer son URL."""
        return bool(obj.cv)

    def validate_hourly_rate(self, value):
        """Refuse un tarif horaire négatif."""
        if value < 0:
            raise serializers.ValidationError(
                "Le tarif horaire ne peut pas être négatif."
            )
        return value


class ProfileAnalysisSerializer(serializers.Serializer):
    """Valide les données de profil envoyées au coach IA."""

    title = serializers.CharField(max_length=120)
    bio = serializers.CharField(max_length=2000)
    skills = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=True,
    )
    hourly_rate = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
    )


class ModerationLogSerializer(serializers.ModelSerializer):
    """Sérialise une entrée de l'historique de modération."""

    class Meta:
        """Déclare les champs de l'historique."""

        model = ModerationLog
        fields = (
            "decision",
            "reason",
            "confidence",
            "criteria",
            "error",
            "created_at",
        )


class ModerationListSerializer(serializers.ModelSerializer):
    """Sérialise un utilisateur dans la liste de modération."""

    last_reason = serializers.SerializerMethodField()

    class Meta:
        """Déclare les champs de la liste."""

        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "title",
            "moderation_status",
            "moderation_checked_at",
            "last_reason",
            "has_cv",
        )

    has_cv = serializers.SerializerMethodField()

    def get_has_cv(self, obj: User) -> bool:
        """Indique si le profil modéré possède un CV."""
        return bool(obj.cv)

    def get_last_reason(self, obj):
        """Retourne la dernière raison ou une chaîne vide."""
        return getattr(obj, "latest_reason", None) or ""


class ModerationDetailSerializer(serializers.ModelSerializer):
    """Sérialise le détail d'un profil et son historique."""

    moderation_logs = ModerationLogSerializer(many=True, read_only=True)
    last_analysis = serializers.SerializerMethodField()

    class Meta:
        """Déclare les champs du détail."""

        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "title",
            "bio",
            "skills",
            "hourly_rate",
            "moderation_status",
            "moderation_logs",
            "last_analysis",
            "has_cv",
        )

    has_cv = serializers.SerializerMethodField()

    def get_has_cv(self, obj: User) -> bool:
        """Indique si le profil détaillé possède un CV."""
        return bool(obj.cv)

    def get_last_analysis(self, obj):
        """Retourne la dernière analyse ou null si aucun journal n'existe."""
        log = obj.moderation_logs.order_by("-created_at", "-id").first()
        if log is None:
            return None
        return ModerationLogSerializer(log).data

    def validate_skills(self, value):
        """Vérifie que les compétences sont une liste de chaînes."""
        if not isinstance(value, list) or not all(
            isinstance(skill, str) for skill in value
        ):
            raise serializers.ValidationError(
                "Les compétences doivent être une liste de chaînes."
            )
        return value
