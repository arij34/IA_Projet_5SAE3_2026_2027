"""Exploitation des résultats de quiz du module challenges.

Ce service lit uniquement les données existantes des challenges ; il
n'écrit rien et ne modifie aucun comportement de ce module.
"""

from challenges.models import QuizAttempt

from ..constants import DEFAULT_QUIZ_INDIRECT_FACTOR
from .text import tokenize, tokenize_all


def load_quiz_profile(user) -> dict:
    """Construit le profil de quiz d'un freelance à partir de ses tentatives.

    Retourne un dictionnaire ``{"by_category": {...}, "global_average": float|None,
    "attempts": int}``. Les catégories sont indexées par leur slug.
    """
    attempts = (
        QuizAttempt.objects.filter(
            user=user,
            status=QuizAttempt.Status.COMPLETED,
            score_percent__isnull=False,
        )
        .select_related("quiz", "quiz__category")
        .only("score_percent", "quiz__category__slug", "quiz__category__name")
    )
    by_category: dict[str, dict] = {}
    scores: list[float] = []
    for attempt in attempts:
        category = attempt.quiz.category
        bucket = by_category.setdefault(
            category.slug,
            {"name": category.name, "scores": []},
        )
        bucket["scores"].append(float(attempt.score_percent))
        scores.append(float(attempt.score_percent))

    for bucket in by_category.values():
        bucket["average"] = sum(bucket["scores"]) / len(bucket["scores"])
        bucket["attempts"] = len(bucket["scores"])

    return {
        "by_category": by_category,
        "global_average": (sum(scores) / len(scores)) if scores else None,
        "attempts": len(scores),
    }


def load_quiz_profiles(users) -> dict[int, dict]:
    """Charge en une requête les profils de quiz de plusieurs freelances."""
    user_ids = [user.pk for user in users]
    attempts = (
        QuizAttempt.objects.filter(
            user_id__in=user_ids,
            status=QuizAttempt.Status.COMPLETED,
            score_percent__isnull=False,
        )
        .select_related("quiz", "quiz__category")
        .only("user_id", "score_percent", "quiz__category__slug", "quiz__category__name")
    )
    raw: dict[int, dict] = {
        user_id: {"by_category": {}, "scores": []} for user_id in user_ids
    }
    for attempt in attempts:
        entry = raw.get(attempt.user_id)
        if entry is None:
            continue
        category = attempt.quiz.category
        bucket = entry["by_category"].setdefault(
            category.slug,
            {"name": category.name, "scores": []},
        )
        bucket["scores"].append(float(attempt.score_percent))
        entry["scores"].append(float(attempt.score_percent))

    profiles: dict[int, dict] = {}
    for user_id, entry in raw.items():
        for bucket in entry["by_category"].values():
            bucket["average"] = sum(bucket["scores"]) / len(bucket["scores"])
            bucket["attempts"] = len(bucket["scores"])
        profiles[user_id] = {
            "by_category": entry["by_category"],
            "global_average": (
                sum(entry["scores"]) / len(entry["scores"])
                if entry["scores"]
                else None
            ),
            "attempts": len(entry["scores"]),
        }
    return profiles


def speciality_quiz_score(
    quiz_profile: dict,
    speciality_names,
    indirect_factor: float = DEFAULT_QUIZ_INDIRECT_FACTOR,
) -> dict:
    """Évalue la compétence démontrée pour les spécialités demandées.

    Retourne ``{"available": bool, "score": float|None, "source": str,
    "categories": [...]}``. Le critère est déclaré indisponible lorsque le
    freelance n'a passé aucun quiz : il ne reçoit alors jamais un score nul.
    """
    by_category = quiz_profile.get("by_category") or {}
    if not by_category:
        return {
            "available": False,
            "score": None,
            "source": "aucune_tentative",
            "categories": [],
            "detail": "Aucun quiz terminé : critère neutralisé.",
        }

    required_tokens = tokenize_all(speciality_names)
    matched: list[dict] = []
    for slug, bucket in by_category.items():
        category_tokens = tokenize(slug) | tokenize(bucket["name"])
        if category_tokens & required_tokens:
            matched.append(
                {
                    "category": slug,
                    "name": bucket["name"],
                    "average": round(bucket["average"], 2),
                    "attempts": bucket["attempts"],
                }
            )

    if matched:
        score = sum(item["average"] for item in matched) / len(matched)
        return {
            "available": True,
            "score": round(score, 2),
            "source": "specialite",
            "categories": matched,
            "detail": "Moyenne des quiz des catégories liées à la spécialité.",
        }

    global_average = quiz_profile.get("global_average")
    return {
        "available": True,
        "score": round(global_average * indirect_factor, 2),
        "source": "indirect",
        "categories": [
            {
                "category": slug,
                "name": bucket["name"],
                "average": round(bucket["average"], 2),
                "attempts": bucket["attempts"],
            }
            for slug, bucket in by_category.items()
        ],
        "detail": (
            "Aucun quiz dans la spécialité : moyenne générale atténuée "
            f"d'un facteur {indirect_factor}."
        ),
    }
