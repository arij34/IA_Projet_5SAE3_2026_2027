"""Routes de l'API du module users."""

from django.urls import path

from .views import (
    LoginView,
    MeView,
    ModerationApproveView,
    ModerationAnalyzeView,
    ModerationDetailView,
    ModerationListView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
]

admin_moderation_urlpatterns = [
    path("", ModerationListView.as_view(), name="moderation-list"),
    path("<int:pk>/", ModerationDetailView.as_view(), name="moderation-detail"),
    path(
        "<int:pk>/approve/",
        ModerationApproveView.as_view(),
        name="moderation-approve",
    ),
    path(
        "<int:pk>/analyze/",
        ModerationAnalyzeView.as_view(),
        name="moderation-analyze",
    ),
]
