"""Routes du module matching, montées sous /api/matching/."""

from django.urls import path

from .views import (
    MyRecommendationListView,
    ProjectFreelancerMatchView,
    ProjectMatchRefreshView,
    ProjectMatchScoreListView,
    ProjectRecommendationCreateView,
    ProjectTeamView,
    RecommendationRespondView,
    RecommendedProjectListView,
    SmartProjectMatchView,
)

app_name = "matching"

urlpatterns = [
    path(
        "projects/<int:pk>/smart-match/",
        SmartProjectMatchView.as_view(),
        name="project-smart-match",
    ),
    path(
        "projects/<int:pk>/freelancers/",
        ProjectFreelancerMatchView.as_view(),
        name="project-freelancers",
    ),
    path(
        "projects/<int:pk>/scores/",
        ProjectMatchScoreListView.as_view(),
        name="project-scores",
    ),
    path(
        "projects/<int:pk>/refresh/",
        ProjectMatchRefreshView.as_view(),
        name="project-refresh",
    ),
    path(
        "projects/<int:pk>/team/",
        ProjectTeamView.as_view(),
        name="project-team",
    ),
    path(
        "projects/<int:pk>/recommendations/",
        ProjectRecommendationCreateView.as_view(),
        name="project-recommendation-create",
    ),
    path(
        "recommended-projects/",
        RecommendedProjectListView.as_view(),
        name="recommended-projects",
    ),
    path(
        "recommendations/",
        MyRecommendationListView.as_view(),
        name="my-recommendations",
    ),
    path(
        "recommendations/<int:pk>/respond/",
        RecommendationRespondView.as_view(),
        name="recommendation-respond",
    ),
]
