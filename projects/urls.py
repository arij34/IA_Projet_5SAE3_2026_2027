"""Routes de l'application projects."""

from django.urls import path

from .views import (
    ProjectAnalyzeView,
    ProjectDecisionView,
    ProjectDetailView,
    ProjectListCreateView,
    PublishedProjectListView,
)


urlpatterns = [
    path("projects/", ProjectListCreateView.as_view(), name="project-list-create"),
    path("projects/published/", PublishedProjectListView.as_view(), name="project-published"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path(
        "projects/<int:pk>/analyze/",
        ProjectAnalyzeView.as_view(),
        name="project-analyze",
    ),
    path(
        "projects/<int:pk>/publish/",
        ProjectDecisionView.as_view(),
        {"decision": "publish"},
        name="project-publish",
    ),
    path(
        "projects/<int:pk>/decline/",
        ProjectDecisionView.as_view(),
        {"decision": "decline"},
        name="project-decline",
    ),
]
