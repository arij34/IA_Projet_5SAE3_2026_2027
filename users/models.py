from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


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

    objects = CustomUserManager()

    def __str__(self):
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
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Options de stockage et d'affichage de l'historique."""

        ordering = ("-created_at",)

    def __str__(self):
        """Retourne un libellé lisible du journal."""
        return f"{self.user.username} - {self.decision}"