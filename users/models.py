from django.contrib.auth.models import AbstractUser, UserManager
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils.deconstruct import deconstructible
from uuid import uuid4

from .validators import validate_cv_file


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """Stockage local des fichiers privés, hors du stockage public."""

    def __init__(self) -> None:
        """Configure le stockage avec le répertoire privé des réglages."""
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


def cv_upload_to(instance: "User", filename: str) -> str:
    """Génère un nom aléatoire et sans donnée issue du nom original."""
    return f"cv/{uuid4().hex}.pdf"


class CustomUserManager(UserManager):
    """Un superuser créé avec createsuperuser est automatiquement ADMIN et validé."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "ADMIN")
        extra_fields.setdefault("moderation_status", "OK")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """Utilisateur de la plateforme Freelancy (freelance, porteur de projet ou admin)."""

    class Role(models.TextChoices):
        FREELANCER = "FREELANCER", "Freelance"
        PROJECT_OWNER = "PROJECT_OWNER", "Porteur de projet"
        ADMIN = "ADMIN", "Administrateur"

    class ModerationStatus(models.TextChoices):
        PENDING = "PENDING", "En attente de vérification"
        OK = "OK", "Validé"
        SUSPECT = "SUSPECT", "Suspect (revue par un admin)"
        REJETE = "REJETE", "Rejeté"

    # AbstractUser ne force pas l'unicité de l'email : on la rend obligatoire.
    email = models.EmailField("adresse e-mail", unique=True)

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.FREELANCER
    )

    # --- Profil (données utilisées par les tâches IA B et C) ---
    title = models.CharField("titre", max_length=120, blank=True)
    bio = models.TextField("biographie", blank=True)
    skills = models.JSONField("compétences", default=list, blank=True)
    hourly_rate = models.DecimalField(
        "tarif horaire", max_digits=8, decimal_places=2, null=True, blank=True
    )

    # --- Modération (tâche IA C) ---
    moderation_status = models.CharField(
        max_length=10,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
    )
    moderation_checked_at = models.DateTimeField(null=True, blank=True)
    cv = models.FileField(
        "CV",
        upload_to=cv_upload_to,
        storage=PrivateMediaStorage(),
        validators=[validate_cv_file],
        null=True,
        blank=True,
    )

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        """Enregistre l'utilisateur et supprime l'ancien CV remplacé."""
        old_cv_name = None
        if self.pk:
            old_cv_name = (
                type(self).objects.filter(pk=self.pk)
                .values_list("cv", flat=True)
                .first()
            )
        super().save(*args, **kwargs)
        if old_cv_name and old_cv_name != self.cv.name:
            self.cv.storage.delete(old_cv_name)

    def delete(self, *args, **kwargs):
        """Supprime le CV du stockage avant de supprimer l'utilisateur."""
        cv_name = self.cv.name
        storage = self.cv.storage
        result = super().delete(*args, **kwargs)
        if cv_name:
            storage.delete(cv_name)
        return result

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"


class ModerationLog(models.Model):
    """Historique des décisions de modération appliquées à un utilisateur."""

    class Decision(models.TextChoices):
        OK = User.ModerationStatus.OK, "Validé"
        SUSPECT = User.ModerationStatus.SUSPECT, "Suspect"
        REJETE = User.ModerationStatus.REJETE, "Rejeté"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="moderation_logs",
    )
    decision = models.CharField(max_length=10, choices=Decision.choices)
    reason = models.TextField()
    confidence = models.FloatField(null=True, blank=True)
    criteria = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Options de stockage et d'affichage de l'historique."""

        ordering = ("-created_at",)

    def __str__(self):
        """Retourne un libellé lisible du journal."""
        return f"{self.user.username} - {self.decision}"