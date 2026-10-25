"""Seed curated Advanced quizzes for each active challenge category."""

from django.db import migrations

from challenges.curated_quizzes import CURATED_ADVANCED_QUIZZES


def seed_advanced_quizzes(apps, schema_editor):
    Category = apps.get_model("challenges", "ChallengeCategory")
    Quiz = apps.get_model("challenges", "Quiz")
    Question = apps.get_model("challenges", "Question")
    AnswerChoice = apps.get_model("challenges", "AnswerChoice")
    db = schema_editor.connection.alias

    for slug, difficulty, title, payload in CURATED_ADVANCED_QUIZZES:
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


class Migration(migrations.Migration):
    dependencies = [("challenges", "0010_supervisor_interaction_triggers")]

    operations = [
        migrations.RunPython(seed_advanced_quizzes, migrations.RunPython.noop),
    ]
