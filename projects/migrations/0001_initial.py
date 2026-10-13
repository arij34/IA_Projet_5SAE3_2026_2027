"""Migration initiale du modèle Project."""

import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    """Crée le modèle Project."""

    initial = True

    dependencies = [
        ("users", "0004_user_cv"),
    ]

    operations = [
        migrations.CreateModel(
            name="Project",
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
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField(max_length=3000)),
                ("deadline", models.DateField()),
                (
                    "estimated_amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.01"))
                        ],
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Brouillon"),
                            ("ANALYZED", "Analysé"),
                            ("PUBLISHED", "Publié"),
                            ("DECLINED", "Refusé"),
                        ],
                        default="DRAFT",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="projects",
                        to="users.user",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
