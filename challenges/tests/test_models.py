"""Tests des contraintes des modèles Challenges."""

from django.db import IntegrityError, transaction
from django.test import TestCase

from challenges.models import AnswerChoice, ChallengeCategory, Question, Quiz


class ChallengeModelTests(TestCase):
    """Vérifie les statuts et les contraintes du catalogue."""

    def setUp(self):
        self.category = ChallengeCategory.objects.create(
            slug="test-category",
            name="Test",
            description="Catégorie de test.",
        )
        self.quiz = Quiz.objects.create(
            category=self.category,
            title="Quiz de test",
            difficulty=Quiz.Difficulty.BEGINNER,
        )

    def test_quiz_defaults_to_draft(self):
        self.assertEqual(self.quiz.status, Quiz.Status.DRAFT)

    def test_question_position_is_unique_within_quiz(self):
        Question.objects.create(quiz=self.quiz, text="Question 1", position=1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Question.objects.create(quiz=self.quiz, text="Question dupliquée", position=1)

    def test_question_can_have_only_one_correct_choice(self):
        question = Question.objects.create(
            quiz=self.quiz,
            text="Question",
            position=1,
        )
        AnswerChoice.objects.create(
            question=question,
            text="Bonne réponse",
            position=1,
            is_correct=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            AnswerChoice.objects.create(
                question=question,
                text="Deuxième bonne réponse",
                position=2,
                is_correct=True,
            )