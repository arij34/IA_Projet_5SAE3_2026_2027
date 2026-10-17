"""Fabriques de données de test propres au module matching."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from challenges.models import (
    AnswerChoice,
    ChallengeCategory,
    Question,
    Quiz,
    QuizAttempt,
)
from projects.models import Project, ProjectAnalysis
from users.models import User

ANALYSIS_RESULT = {
    "budget_min": 8000,
    "budget_max": 12000,
    "budget_recommande": 10000,
    "devise": "EUR",
    "nb_freelancers": 2,
    "duree_semaines": 10,
    "complexite": "MOYENNE",
    "specialites": [
        {
            "nom": "Python",
            "nb": 1,
            "niveau": "CONFIRME",
            "charge_pourcentage": 60.0,
        },
        {
            "nom": "React",
            "nb": 1,
            "niveau": "JUNIOR",
            "charge_pourcentage": 40.0,
        },
    ],
}


def make_freelancer(username: str, **kwargs) -> User:
    """Crée un freelance validé par défaut."""
    defaults = {
        "email": f"{username}@example.test",
        "role": User.Role.FREELANCER,
        "moderation_status": User.ModerationStatus.OK,
        "title": "Développeur",
        "bio": "Profil de test.",
        "skills": ["Python", "Django"],
        "hourly_rate": Decimal("40.00"),
    }
    defaults.update(kwargs)
    user = User.objects.create_user(username=username, password="x", **defaults)
    return user


def make_owner(username: str = "owner") -> User:
    """Crée un porteur de projet validé."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="x",
        role=User.Role.PROJECT_OWNER,
        moderation_status=User.ModerationStatus.OK,
    )


def make_project(owner: User, status: str = Project.Status.PUBLISHED, **kwargs) -> Project:
    """Crée un projet appartenant au porteur donné."""
    defaults = {
        "name": "Plateforme de test",
        "description": "Application web Python et React pour une équipe interne.",
        "deadline": timezone.localdate() + timedelta(days=120),
        "estimated_amount": Decimal("10000.00"),
        "status": status,
    }
    defaults.update(kwargs)
    return Project.objects.create(owner=owner, **defaults)


def make_analysis(project: Project, result: dict | None = None) -> ProjectAnalysis:
    """Attache une analyse réussie à un projet."""
    return ProjectAnalysis.objects.create(
        project=project,
        result=result if result is not None else dict(ANALYSIS_RESULT),
        simulated=True,
        error=None,
    )


def make_quiz_attempt(user: User, category_slug: str, score: int) -> QuizAttempt:
    """Crée une tentative terminée dans une catégorie donnée."""
    category, _ = ChallengeCategory.objects.get_or_create(
        slug=category_slug,
        defaults={
            "name": category_slug.capitalize(),
            "description": "Catégorie de test.",
        },
    )
    quiz = Quiz.objects.create(
        category=category,
        title=f"Quiz {category_slug} {score}",
        difficulty=Quiz.Difficulty.INTERMEDIATE,
        status=Quiz.Status.PUBLISHED,
    )
    question = Question.objects.create(quiz=quiz, text="Question ?", position=1)
    AnswerChoice.objects.create(
        question=question, text="Bonne", position=1, is_correct=True
    )
    return QuizAttempt.objects.create(
        user=user,
        quiz=quiz,
        status=QuizAttempt.Status.COMPLETED,
        total_questions=1,
        correct_answers=1 if score >= 50 else 0,
        score_percent=score,
        completed_at=timezone.now(),
    )
