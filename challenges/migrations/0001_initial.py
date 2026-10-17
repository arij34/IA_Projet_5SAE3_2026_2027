"""Create challenge catalog and initial categories."""

from django.db import migrations, models
import django.db.models.deletion


INITIAL_CATEGORIES = (
    (
        "python",
        "Python",
        "Testez les fondamentaux du langage, les collections et les pratiques Python.",
    ),
    (
        "django",
        "Django",
        "Explorez les modèles, les vues, les API et les tests avec Django.",
    ),
    (
        "react",
        "React",
        "Mettez en pratique les composants, les hooks et les interfaces React.",
    ),
    (
        "typescript",
        "TypeScript",
        "Progressez sur les types, le narrowing et les fonctionnalités TypeScript.",
    ),
)


def seed_categories(apps, schema_editor):
    ChallengeCategory = apps.get_model("challenges", "ChallengeCategory")
    database = schema_editor.connection.alias
    for position, (slug, name, description) in enumerate(INITIAL_CATEGORIES):
        ChallengeCategory.objects.using(database).get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "display_order": position,
            },
        )


def remove_seed_categories(apps, schema_editor):
    ChallengeCategory = apps.get_model("challenges", "ChallengeCategory")
    database = schema_editor.connection.alias
    ChallengeCategory.objects.using(database).filter(
        slug__in=[slug for slug, _, _ in INITIAL_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ChallengeCategory",
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
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ("display_order", "name")},
        ),
        migrations.RunPython(seed_categories, remove_seed_categories),
        migrations.CreateModel(
            name="Quiz",
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
                ("title", models.CharField(max_length=180)),
                (
                    "difficulty",
                    models.CharField(
                        choices=[
                            ("BEGINNER", "Débutant"),
                            ("INTERMEDIATE", "Intermédiaire"),
                            ("ADVANCED", "Avancé"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Brouillon"),
                            ("PUBLISHED", "Publié"),
                            ("ARCHIVED", "Archivé"),
                        ],
                        default="DRAFT",
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quizzes",
                        to="challenges.challengecategory",
                    ),
                ),
            ],
            options={
                "ordering": ("category__display_order", "difficulty", "title")
            },
        ),
        migrations.CreateModel(
            name="Question",
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
                ("text", models.TextField()),
                ("position", models.PositiveSmallIntegerField()),
                ("explanation", models.TextField(blank=True)),
                (
                    "quiz",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="challenges.quiz",
                    ),
                ),
            ],
            options={"ordering": ("position",)},
        ),
        migrations.CreateModel(
            name="AnswerChoice",
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
                ("text", models.CharField(max_length=500)),
                ("position", models.PositiveSmallIntegerField()),
                ("is_correct", models.BooleanField(default=False)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="choices",
                        to="challenges.question",
                    ),
                ),
            ],
            options={"ordering": ("position",)},
        ),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.UniqueConstraint(
                fields=("quiz", "position"),
                name="challenge_question_quiz_pos_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="answerchoice",
            constraint=models.UniqueConstraint(
                fields=("question", "position"),
                name="challenge_choice_question_pos_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="answerchoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_correct=True),
                fields=("question",),
                name="challenge_choice_one_correct",
            ),
        ),
    ]