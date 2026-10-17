"""Seed one curated quiz to make the Challenges flow playable."""

from django.db import migrations


QUIZ_TITLE = "Python : les fondamentaux"
QUESTIONS = (
    (
        "Lequel de ces types intégrés est mutable en Python ?",
        (("tuple", False), ("list", True), ("str", False), ("int", False)),
        "Une liste peut être modifiée après sa création, contrairement aux tuples, chaînes et entiers.",
    ),
    (
        "Que renvoie len([2, 4, 6]) ?",
        (("2", False), ("3", True), ("6", False), ("12", False)),
        "La liste contient trois éléments, donc len renvoie 3.",
    ),
    (
        "Quelle expression crée un dictionnaire associant la clé x à la valeur 1 ?",
        (
            ('{"x": 1}', True),
            ('["x", 1]', False),
            ('("x", 1)', False),
            ('{"x"}', False),
        ),
        "Un dictionnaire associe ses clés et valeurs avec deux-points entre accolades.",
    ),
)


def seed_quiz(apps, schema_editor):
    ChallengeCategory = apps.get_model("challenges", "ChallengeCategory")
    Quiz = apps.get_model("challenges", "Quiz")
    Question = apps.get_model("challenges", "Question")
    AnswerChoice = apps.get_model("challenges", "AnswerChoice")
    database = schema_editor.connection.alias
    category = ChallengeCategory.objects.using(database).filter(slug="python").first()
    if category is None:
        return

    quiz, created = Quiz.objects.using(database).get_or_create(
        category=category,
        title=QUIZ_TITLE,
        difficulty="BEGINNER",
        defaults={"status": "PUBLISHED"},
    )
    if not created:
        return

    for question_position, (text, choices, explanation) in enumerate(QUESTIONS, 1):
        question = Question.objects.using(database).create(
            quiz=quiz,
            text=text,
            position=question_position,
            explanation=explanation,
        )
        AnswerChoice.objects.using(database).bulk_create(
            [
                AnswerChoice(
                    question=question,
                    text=choice_text,
                    position=choice_position,
                    is_correct=is_correct,
                )
                for choice_position, (choice_text, is_correct) in enumerate(choices, 1)
            ]
        )


def remove_quiz(apps, schema_editor):
    ChallengeCategory = apps.get_model("challenges", "ChallengeCategory")
    Quiz = apps.get_model("challenges", "Quiz")
    database = schema_editor.connection.alias
    Quiz.objects.using(database).filter(
        category__slug="python",
        title=QUIZ_TITLE,
        difficulty="BEGINNER",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("challenges", "0002_quizattempt_submittedanswer_and_more"),
    ]

    operations = [migrations.RunPython(seed_quiz, remove_quiz)]