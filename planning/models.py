from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models


class PlanningProject(models.Model):
    """A user's saved planning, isolated from the projects app."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="planning_projects",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "id")

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    """A task belonging to one saved planning project."""

    project = models.ForeignKey(
        PlanningProject,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    name = models.CharField(max_length=100, validators=[MinLengthValidator(3)])
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ("start_date", "id")

    def __str__(self) -> str:
        return self.name
