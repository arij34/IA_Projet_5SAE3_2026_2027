"""Modèles du catalogue de challenges techniques."""

from django.conf import settings
from django.db import models


class ChallengeCategory(models.Model):
    """Catégorie affichable dans le catalogue des challenges."""

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        """Ordre stable du catalogue."""

        ordering = ("display_order", "name")

    def __str__(self) -> str:
        return self.name


class Quiz(models.Model):
    """Quiz associé à une catégorie et une difficulté."""

    class Difficulty(models.TextChoices):
        BEGINNER = "BEGINNER", "Débutant"
        INTERMEDIATE = "INTERMEDIATE", "Intermédiaire"
        ADVANCED = "ADVANCED", "Avancé"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        PUBLISHED = "PUBLISHED", "Publié"
        ARCHIVED = "ARCHIVED", "Archivé"

    category = models.ForeignKey(
        ChallengeCategory,
        on_delete=models.PROTECT,
        related_name="quizzes",
    )
    title = models.CharField(max_length=180)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    class Source(models.TextChoices):
        CURATED = "CURATED", "Curaté"
        AI_GENERATED = "AI_GENERATED", "Généré par IA"

    source = models.CharField(
        max_length=12,
        choices=Source.choices,
        default=Source.CURATED,
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_challenge_quizzes",
    )
    llm_provider = models.CharField(max_length=20, blank=True)
    llm_model = models.CharField(max_length=80, blank=True)
    prompt_version = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Ordre stable des quiz."""

        ordering = ("category__display_order", "difficulty", "title")

    def __str__(self) -> str:
        return f"{self.title} ({self.get_difficulty_display()})"


class Question(models.Model):
    """Question d'un quiz; la correction reste privée côté API."""

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField()
    position = models.PositiveSmallIntegerField()
    explanation = models.TextField(blank=True)

    class Meta:
        """Ordre et unicité des questions dans un quiz."""

        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("quiz", "position"),
                name="challenge_question_quiz_pos_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quiz}: question {self.position}"


class AnswerChoice(models.Model):
    """Choix de réponse, avec correction privée au niveau du modèle."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    text = models.CharField(max_length=500)
    position = models.PositiveSmallIntegerField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        """Ordre et contraintes des choix d'une question."""

        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("question", "position"),
                name="challenge_choice_question_pos_uniq",
            ),
            models.UniqueConstraint(
                fields=("question",),
                condition=models.Q(is_correct=True),
                name="challenge_choice_one_correct",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.question}: choix {self.position}"


class QuizAttempt(models.Model):
    """Tentative personnelle d'un quiz par un freelancer."""

    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        COMPLETED = "COMPLETED", "Terminée"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenge_attempts",
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    total_questions = models.PositiveSmallIntegerField()
    correct_answers = models.PositiveSmallIntegerField(default=0)
    score_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Latest attempts first and at most one active attempt per quiz/user."""

        ordering = ("-started_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "quiz"),
                condition=models.Q(status="IN_PROGRESS"),
                name="challenge_one_active_attempt_per_quiz",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.quiz} ({self.get_status_display()})"


class SubmittedAnswer(models.Model):
    """A single immutable answer, with correctness calculated by the server."""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="submitted_answers",
    )
    selected_choice = models.ForeignKey(
        AnswerChoice,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    is_correct = models.BooleanField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """A question may be answered only once per attempt."""

        ordering = ("question__position",)
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "question"),
                name="challenge_one_answer_per_question_attempt",
            ),
        ]

    def __str__(self) -> str:
        return f"Attempt {self.attempt_id}, question {self.question_id}"


class SupervisorEvent(models.Model):
    """Persist an eligible supervisor trigger without answer content."""

    class TriggerType(models.TextChoices):
        REPEATED_ERRORS = "repeated_errors", "Repeated errors"
        POSITIVE_FEEDBACK = "positive_feedback", "Positive feedback"
        SLOW_PROGRESS = "slow_progress", "Slow progress"
        REPEATED_ANSWER_CHANGES = "repeated_answer_changes", "Repeated answer changes"
        LONG_RESPONSE = "long_response", "Long response"
        MULTIPLE_TIMEOUTS = "multiple_timeouts", "Multiple timeouts"

    class GenerationStatus(models.TextChoices):
        PENDING = "PENDING", "En attente"
        GENERATING = "GENERATING", "Génération en cours"
        GENERATED = "GENERATED", "Généré"
        FALLBACK = "FALLBACK", "Message de secours"
        SUPPRESSED = "SUPPRESSED", "Supprimé"

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="supervisor_events",
    )
    source_answer = models.OneToOneField(
        SubmittedAnswer,
        on_delete=models.CASCADE,
        related_name="supervisor_event",
    )
    trigger_type = models.CharField(max_length=24, choices=TriggerType.choices)
    event_key = models.CharField(max_length=100)
    slot = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    generation_status = models.CharField(
        max_length=12,
        choices=GenerationStatus.choices,
        default=GenerationStatus.PENDING,
    )
    message = models.CharField(max_length=240, blank=True)
    prompt_version = models.CharField(max_length=32, blank=True)
    llm_provider = models.CharField(max_length=20, blank=True)
    llm_model = models.CharField(max_length=80, blank=True)
    generation_error_code = models.CharField(max_length=32, blank=True)
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    generation_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Database-enforced identity, one-per-trigger, and two-event cap."""

        ordering = ("slot",)
        constraints = [
            models.UniqueConstraint(
                fields=("event_key",),
                name="challenge_supervisor_event_key_uniq",
            ),
            models.UniqueConstraint(
                fields=("attempt", "trigger_type"),
                name="challenge_supervisor_attempt_trigger_uniq",
            ),
            models.UniqueConstraint(
                fields=("attempt", "slot"),
                name="challenge_supervisor_attempt_slot_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(slot__gte=1, slot__lte=2),
                name="challenge_supervisor_slot_1_2",
            ),
        ]

    def __str__(self) -> str:
        return f"Attempt {self.attempt_id}: {self.trigger_type}"


class SupervisorConnectionTicket(models.Model):
    """Single-use, attempt-scoped credentials for a WebSocket connection."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supervisor_connection_tickets",
    )
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="supervisor_connection_tickets",
    )
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Supervisor ticket for attempt {self.attempt_id}"


class QuestionInteraction(models.Model):
    """Server-timestamped interaction facts for one question of one attempt."""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="interactions",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="interactions",
    )
    displayed_at = models.DateTimeField()
    first_selected_at = models.DateTimeField(null=True, blank=True)
    last_selected_choice_id = models.PositiveIntegerField(null=True, blank=True)
    answer_changes = models.PositiveSmallIntegerField(default=0)
    timed_out = models.BooleanField(default=False)
    timed_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "question"),
                name="unique_interaction_per_attempt_question",
            )
        ]
