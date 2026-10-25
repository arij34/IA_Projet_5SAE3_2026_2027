"""Add JavaScript, SQL, and Git categories with curated Advanced quizzes."""

from django.db import migrations

from challenges.curated_quizzes import CURATED_NEW_CATEGORY_QUIZZES


CATEGORIES = (
    (
        "javascript",
        "JavaScript",
        "Asynchronisme, objets, modules et mécanismes avancés du langage JavaScript.",
        4,
    ),
    (
        "sql",
        "SQL",
        "Requêtes analytiques, index, contraintes et transactions SQL.",
        5,
    ),
    (
        "git",
        "Git",
        "Historique, intégration et collaboration avancés avec Git.",
        6,
    ),
)


def seed_new_categories_and_quizzes(apps, schema_editor):
    Category = apps.get_model("challenges", "ChallengeCategory")
    Quiz = apps.get_model("challenges", "Quiz")
    Question = apps.get_model("challenges", "Question")
    AnswerChoice = apps.get_model("challenges", "AnswerChoice")
    db = schema_editor.connection.alias

    for slug, name, description, display_order in CATEGORIES:
        Category.objects.using(db).get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "display_order": display_order,
                "is_active": True,
            },
        )

    for slug, difficulty, title, payload in CURATED_NEW_CATEGORY_QUIZZES:
        category = Category.objects.using(db).filter(slug=slug, is_active=True).first()
        if category is None:
            continue
        quiz, created = Quiz.objects.using(db).get_or_create(
            category=category,
            title=title,
            difficulty=difficulty,
            defaults={"status": "PUBLISHED", "source": "CURATED"},
        )
        if not created:
            continue
        for position, item in enumerate(payload["questions"], start=1):
            question = Question.objects.using(db).create(
                quiz=quiz,
                text=item["text"],
                position=position,
                explanation=item["explanation"],
            )
            AnswerChoice.objects.using(db).bulk_create(
                AnswerChoice(
                    question=question,
                    text=text,
                    position=index + 1,
                    is_correct=index == item["correct_index"],
                )
                for index, text in enumerate(item["choices"])
            )


class Migration(migrations.Migration):
    dependencies = [("challenges", "0011_seed_advanced_quizzes")]

    operations = [
        migrations.RunPython(
            seed_new_categories_and_quizzes,
            migrations.RunPython.noop,
        ),
    ]
