"""Routes de l'API du module users."""

from django.urls import path

from .views import (
    LoginView,
    MyCvView,
    MeView,
    ModerationApproveView,
    ModerationAnalyzeView,
    ModerationDetailView,
    ModerationListView,
    ProfileAnalysisView,
    RegisterView,
    AdminUserCvView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("me/cv/", MyCvView.as_view(), name="my-cv"),
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

admin_cv_urlpatterns = [
    path("<int:pk>/cv/", AdminUserCvView.as_view(), name="admin-user-cv"),
]

ai_urlpatterns = [
    path("profile-analysis/", ProfileAnalysisView.as_view(), name="profile-analysis"),
]
