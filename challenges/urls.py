"""Routes de lecture de l'application challenges."""

from django.urls import path

from .views import (
    GenerateQuizView,
    ChallengeCategoryListView,
    PublishedQuizDetailView,
    PublishedQuizListView,
    QuizAttemptAnswerView,
    QuizAttemptCompleteView,
    QuizAttemptCreateView,
    QuizAttemptDetailView,
    QuizAttemptInteractionView,
    QuizAttemptMetricsView,
    QuizAttemptResultView,
    SupervisorConnectionTicketView,
)


urlpatterns = [
    path("categories/", ChallengeCategoryListView.as_view(), name="category-list"),
    path("quizzes/", PublishedQuizListView.as_view(), name="quiz-list"),
    path("quizzes/generate/", GenerateQuizView.as_view(), name="quiz-generate"),
    path("quizzes/<int:pk>/", PublishedQuizDetailView.as_view(), name="quiz-detail"),
    path("attempts/", QuizAttemptCreateView.as_view(), name="attempt-create"),
    path("attempts/<int:pk>/", QuizAttemptDetailView.as_view(), name="attempt-detail"),
    path(
        "attempts/<int:pk>/supervisor-ticket/",
        SupervisorConnectionTicketView.as_view(),
        name="supervisor-ticket",
    ),
    path("attempts/<int:pk>/answers/", QuizAttemptAnswerView.as_view(), name="attempt-answer"),
    path("attempts/<int:pk>/interactions/", QuizAttemptInteractionView.as_view(), name="attempt-interaction"),
    path("attempts/<int:pk>/metrics/", QuizAttemptMetricsView.as_view(), name="attempt-metrics"),
    path("attempts/<int:pk>/complete/", QuizAttemptCompleteView.as_view(), name="attempt-complete"),
    path("attempts/<int:pk>/results/", QuizAttemptResultView.as_view(), name="attempt-results"),
]