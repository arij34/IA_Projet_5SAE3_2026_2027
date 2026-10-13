"""Ajoute l'historique des analyses de projets."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Crée le modèle ProjectAnalysis."""

    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectAnalysis",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("result", models.JSONField(blank=True, null=True)),
                ("simulated", models.BooleanField(default=False)),
                ("error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analyses",
                        to="projects.project",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
