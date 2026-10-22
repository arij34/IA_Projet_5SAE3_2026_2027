from django.urls import path

from .views import (
    GeneratePlanningView,
    PlanningProjectDetailView,
    PlanningProjectListCreateView,
    PlanningTaskDetailView,
)


app_name = "planning"

urlpatterns = [
    path("generate/", GeneratePlanningView.as_view(), name="generate"),
    path("", PlanningProjectListCreateView.as_view(), name="project-list-create"),
    path("<int:pk>/", PlanningProjectDetailView.as_view(), name="project-detail"),
    path(
        "<int:project_id>/tasks/<int:task_id>/",
        PlanningTaskDetailView.as_view(),
        name="task-detail",
    ),
]
