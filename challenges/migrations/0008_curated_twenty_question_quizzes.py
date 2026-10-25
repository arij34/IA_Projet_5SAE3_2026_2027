"""Unpublish quizzes that do not have exactly 20 questions and seed curated 20-question quizzes."""

from django.db import migrations
from django.db.models import Count

from challenges.curated_quizzes import CURATED_QUIZZES, QUESTIONS_PER_QUIZ


def unpublish_incomplete(apps, schema_editor):
    Quiz = apps.get_model("challenges", "Quiz")
    db = schema_editor.connection.alias
    incomplete = (
        Quiz.objects.using(db)
        .filter(status="PUBLISHED")
        .annotate(total=Count("questions"))
        .exclude(total=QUESTIONS_PER_QUIZ)
    )
    # Archived as drafts, not deleted: existing attempts keep their history.
    Quiz.objects.using(db).filter(pk__in=[quiz.pk for quiz in incomplete]).update(status="DRAFT")


def seed_curated(apps, schema_editor):
    Category = apps.get_model("challenges", "ChallengeCategory")
    Quiz = apps.get_model("challenges", "Quiz")
    Question = apps.get_model("challenges", "Question")
    AnswerChoice = apps.get_model("challenges", "AnswerChoice")
    db = schema_editor.connection.alias
    for slug, difficulty, title, payload in CURATED_QUIZZES:
        category = Category.objects.using(db).filter(slug=slug).first()
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


def forward(apps, schema_editor):
    unpublish_incomplete(apps, schema_editor)
    seed_curated(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("challenges", "0007_supervisorevent_acknowledged_at_and_more"),
    ]

    # Not reversible automatically: the previous publication state is not recorded.
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
