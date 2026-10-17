"""Sérialiseurs publics du catalogue de challenges."""

from rest_framework import serializers

from .models import (
    AnswerChoice,
    ChallengeCategory,
    Question,
    Quiz,
    QuizAttempt,
    SubmittedAnswer,
)


class ChallengeCategorySerializer(serializers.ModelSerializer):
    """Expose les catégories actives et les difficultés prises en charge."""

    difficulties = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeCategory
        fields = ("id", "slug", "name", "description", "difficulties")

    def get_difficulties(self, obj: ChallengeCategory) -> list[dict[str, str]]:
        return [
            {"value": value, "label": label}
            for value, label in Quiz.Difficulty.choices
        ]


class PublicAnswerChoiceSerializer(serializers.ModelSerializer):
    """Expose le texte d'un choix sans son indicateur de correction."""

    class Meta:
        model = AnswerChoice
        fields = ("id", "text", "position")


class PublicQuestionSerializer(serializers.ModelSerializer):
    """Expose une question sans correction ni explication."""

    choices = PublicAnswerChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ("id", "text", "position", "choices")


class PublicQuizListSerializer(serializers.ModelSerializer):
    """Expose les métadonnées publiques d'un quiz publié."""

    category = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Quiz
        fields = ("id", "title", "category", "difficulty", "question_count")


class PublicQuizDetailSerializer(PublicQuizListSerializer):
    """Expose le contenu du quiz publié sans aucune réponse officielle."""

    questions = PublicQuestionSerializer(many=True, read_only=True)

    class Meta(PublicQuizListSerializer.Meta):
        fields = PublicQuizListSerializer.Meta.fields + ("questions",)


class GenerateQuizSerializer(serializers.Serializer):
    """Validate the only inputs a freelancer controls for AI generation."""

    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=ChallengeCategory.objects.filter(is_active=True),
    )
    difficulty = serializers.ChoiceField(choices=Quiz.Difficulty.choices)


class StartAttemptSerializer(serializers.Serializer):
    """Validate that the requested quiz is currently available."""

    quiz_id = serializers.PrimaryKeyRelatedField(
        source="quiz",
        queryset=Quiz.objects.filter(
            status=Quiz.Status.PUBLISHED,
            category__is_active=True,
        ),
    )


class SubmitAnswerSerializer(serializers.Serializer):
    """Validate question and choice ownership within this attempt's quiz."""

    question_id = serializers.PrimaryKeyRelatedField(
        source="question",
        queryset=Question.objects.all(),
    )
    choice_id = serializers.PrimaryKeyRelatedField(
        source="selected_choice",
        queryset=AnswerChoice.objects.all(),
    )

    def validate(self, attrs):
        attempt: QuizAttempt = self.context["attempt"]
        question: Question = attrs["question"]
        choice: AnswerChoice = attrs["selected_choice"]
        if question.quiz_id != attempt.quiz_id:
            raise serializers.ValidationError(
                {"question_id": "Cette question n'appartient pas au quiz."}
            )
        if choice.question_id != question.pk:
            raise serializers.ValidationError(
                {"choice_id": "Ce choix n'appartient pas à la question."}
            )
        return attrs


class AttemptQuestionSerializer(PublicQuestionSerializer):
    """Expose the quiz question and any previously submitted choice only."""

    selected_choice_id = serializers.SerializerMethodField()

    class Meta(PublicQuestionSerializer.Meta):
        fields = PublicQuestionSerializer.Meta.fields + ("selected_choice_id",)

    def get_selected_choice_id(self, obj: Question) -> int | None:
        selected_choices = self.context.get("selected_choices", {})
        return selected_choices.get(obj.pk)


class QuizAttemptDetailSerializer(serializers.ModelSerializer):
    """Return resumable attempt state without answer correctness."""

    quiz_title = serializers.CharField(source="quiz.title", read_only=True)
    category = serializers.SlugRelatedField(
        source="quiz.category",
        slug_field="slug",
        read_only=True,
    )
    difficulty = serializers.CharField(source="quiz.difficulty", read_only=True)
    answered_count = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = (
            "id",
            "quiz_title",
            "category",
            "difficulty",
            "status",
            "total_questions",
            "answered_count",
            "started_at",
            "completed_at",
            "questions",
        )

    def get_answered_count(self, obj: QuizAttempt) -> int:
        return obj.answers.count()

    def get_questions(self, obj: QuizAttempt) -> list[dict]:
        selected_choices = dict(
            obj.answers.values_list("question_id", "selected_choice_id")
        )
        questions = obj.quiz.questions.prefetch_related("choices").all()
        return AttemptQuestionSerializer(
            questions,
            many=True,
            context={"selected_choices": selected_choices},
        ).data


class SubmittedAnswerReceiptSerializer(serializers.ModelSerializer):
    """Return a receipt without revealing whether the submitted answer is right."""

    class Meta:
        model = SubmittedAnswer
        fields = ("id", "question_id", "selected_choice_id", "submitted_at")


class QuizAttemptCompletionSerializer(serializers.ModelSerializer):
    """Expose the final aggregate score after completion."""

    class Meta:
        model = QuizAttempt
        fields = (
            "id",
            "status",
            "correct_answers",
            "total_questions",
            "score_percent",
            "completed_at",
        )


class AttemptResultAnswerSerializer(serializers.ModelSerializer):
    """Expose answer correctness and explanation only in completed results."""

    question_id = serializers.IntegerField(read_only=True)
    question_text = serializers.CharField(source="question.text", read_only=True)
    selected_choice_text = serializers.CharField(
        source="selected_choice.text",
        read_only=True,
    )
    correct_choice_text = serializers.SerializerMethodField()
    explanation = serializers.CharField(source="question.explanation", read_only=True)

    class Meta:
        model = SubmittedAnswer
        fields = (
            "question_id",
            "question_text",
            "selected_choice_id",
            "selected_choice_text",
            "is_correct",
            "correct_choice_text",
            "explanation",
        )

    def get_correct_choice_text(self, obj: SubmittedAnswer) -> str:
        correct_choice = obj.question.choices.filter(is_correct=True).first()
        return correct_choice.text if correct_choice else ""


class QuizAttemptResultSerializer(serializers.ModelSerializer):
    """Return a completed quiz result and per-question review."""

    quiz_title = serializers.CharField(source="quiz.title", read_only=True)
    answers = AttemptResultAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = (
            "id",
            "quiz_title",
            "correct_answers",
            "total_questions",
            "score_percent",
            "completed_at",
            "answers",
        )