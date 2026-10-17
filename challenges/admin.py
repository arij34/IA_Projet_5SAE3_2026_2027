"""Administration du catalogue de challenges."""

from django.contrib import admin

from .models import AnswerChoice, ChallengeCategory, Question, Quiz


class QuestionInline(admin.TabularInline):
    """Édition des questions depuis le quiz."""

    model = Question
    extra = 0


class AnswerChoiceInline(admin.TabularInline):
    """Édition des choix depuis la question."""

    model = AnswerChoice
    extra = 0


@admin.register(ChallengeCategory)
class ChallengeCategoryAdmin(admin.ModelAdmin):
    """Gestion des catégories affichées dans le catalogue."""

    list_display = ("name", "slug", "is_active", "display_order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Gestion des quiz sans exposer leurs réponses à l'API publique."""

    list_display = ("title", "category", "difficulty", "status", "created_at")
    list_filter = ("status", "difficulty", "category")
    search_fields = ("title", "category__name")
    inlines = (QuestionInline,)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Gestion des questions et de leurs choix privés."""

    list_display = ("quiz", "position", "text")
    list_filter = ("quiz__category", "quiz__difficulty")
    inlines = (AnswerChoiceInline,)


@admin.register(AnswerChoice)
class AnswerChoiceAdmin(admin.ModelAdmin):
    """Consultation directe des choix et de leur correction par les admins."""

    list_display = ("question", "position", "is_correct")
    list_filter = ("is_correct", "question__quiz__category")