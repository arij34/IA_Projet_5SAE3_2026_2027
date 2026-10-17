"""Orchestration du matching : sélection, scoring et persistance.

Les freelances candidats sont filtrés côté serveur : rôle freelance et
statut de modération validé. Les documents privés ne sont jamais chargés.
"""

import logging

from django.db import transaction
from django.utils import timezone

from projects.models import Project
from users.models import User

from ..constants import ALGORITHM_VERSION
from ..models import MatchScore
from . import semantic_matching
from .quiz_scoring import load_quiz_profiles
from .scoring import best_speciality_score, explain, get_weights, score_speciality

logger = logging.getLogger(__name__)

# Champs strictement nécessaires au scoring : le CV n'est jamais chargé.
FREELANCER_FIELDS = (
    "id",
    "username",
    "title",
    "bio",
    "skills",
    "hourly_rate",
    "role",
    "moderation_status",
)


def eligible_freelancers():
    """Retourne les freelances autorisés à apparaître dans une recommandation."""
    return User.objects.filter(
        role=User.Role.FREELANCER,
        moderation_status=User.ModerationStatus.OK,
        is_active=True,
    ).only(*FREELANCER_FIELDS)


def latest_analysis_result(project: Project) -> dict | None:
    """Retourne le résultat de la dernière analyse réussie d'un projet."""
    analysis = (
        project.analyses.filter(result__isnull=False)
        .exclude(error__isnull=False, error__gt="")
        .order_by("-created_at")
        .first()
    )
    if analysis is None or not isinstance(analysis.result, dict):
        return None
    return analysis.result


def score_candidate(
    project: Project,
    analysis: dict,
    freelancer,
    quiz_profile: dict,
    weights: dict | None = None,
    use_semantic: bool = False,
    speciality: dict | None = None,
) -> dict:
    """Calcule le score complet d'un freelance pour un projet."""
    if speciality is not None:
        deterministic = score_speciality(
            analysis, speciality, freelancer, quiz_profile, weights
        )
        deterministic["all_specialities"] = [
            {
                "speciality": deterministic["speciality"],
                "score": deterministic["deterministic_score"],
            }
        ]
    else:
        deterministic = best_speciality_score(
            analysis, freelancer, quiz_profile, weights
        )

    semantic = (
        semantic_matching.evaluate(project, analysis, freelancer)
        if use_semantic
        else {"available": False, "score": None, "reason": "non_demande"}
    )
    blended = semantic_matching.blend(
        deterministic["deterministic_score"], semantic
    )

    return {
        "freelancer_id": freelancer.pk,
        "username": freelancer.username,
        "title": freelancer.title,
        "hourly_rate": (
            float(freelancer.hourly_rate)
            if freelancer.hourly_rate is not None
            else None
        ),
        "skills": list(freelancer.skills or []),
        "speciality": deterministic["speciality"],
        "required_level": deterministic["required_level"],
        "total_score": blended["total"],
        "deterministic_score": deterministic["deterministic_score"],
        "semantic_score": semantic.get("score"),
        "semantic_available": bool(semantic.get("available")),
        "semantic_justification": semantic.get("justification"),
        "semantic_concepts": semantic.get("concepts", []),
        "mode": blended["mode"],
        "semantic_weight": blended["semantic_weight"],
        "subscores": deterministic["subscores"],
        "applied_weights": deterministic["applied_weights"],
        "skipped_criteria": deterministic["skipped_criteria"],
        "speciality_scores": deterministic.get("all_specialities", []),
        "explanations": explain(deterministic),
        "algorithm_version": ALGORITHM_VERSION,
    }


def rank_freelancers(
    project: Project,
    analysis: dict,
    use_semantic: bool = False,
    limit: int | None = None,
) -> list:
    """Classe les freelances éligibles pour un projet, du meilleur au moins bon."""
    candidates = list(eligible_freelancers())
    if not candidates:
        return []
    quiz_profiles = load_quiz_profiles(candidates)
    weights = get_weights()
    results = [
        score_candidate(
            project,
            analysis,
            freelancer,
            quiz_profiles.get(freelancer.pk, {}),
            weights,
            use_semantic,
        )
        for freelancer in candidates
    ]
    results.sort(key=lambda item: (-item["total_score"], item["freelancer_id"]))
    return results[:limit] if limit else results


@transaction.atomic
def persist_scores(project: Project, results: list) -> int:
    """Enregistre ou met à jour les scores calculés d'un projet."""
    stored = 0
    for item in results:
        MatchScore.objects.update_or_create(
            project=project,
            freelancer_id=item["freelancer_id"],
            speciality=item["speciality"] or "",
            defaults={
                "total_score": item["total_score"],
                "deterministic_score": item["deterministic_score"],
                "semantic_score": item["semantic_score"],
                "mode": item["mode"],
                "breakdown": {
                    "subscores": item["subscores"],
                    "applied_weights": item["applied_weights"],
                    "skipped_criteria": item["skipped_criteria"],
                    "speciality_scores": item["speciality_scores"],
                    "explanations": item["explanations"],
                    "semantic": {
                        "available": item["semantic_available"],
                        "score": item["semantic_score"],
                        "justification": item["semantic_justification"],
                        "concepts": item["semantic_concepts"],
                        "weight": item["semantic_weight"],
                    },
                    "computed_at": timezone.now().isoformat(),
                },
                "algorithm_version": item["algorithm_version"],
            },
        )
        stored += 1
    return stored


def rank_projects_for_freelancer(
    freelancer,
    quiz_profile: dict,
    use_semantic: bool = False,
    limit: int | None = None,
) -> list:
    """Classe les projets publiés et analysés adaptés à un freelance."""
    projects = (
        Project.objects.filter(status=Project.Status.PUBLISHED)
        .prefetch_related("analyses")
        .order_by("-created_at")
    )
    weights = get_weights()
    results = []
    for project in projects:
        analysis = latest_analysis_result(project)
        if not analysis:
            continue
        scored = score_candidate(
            project, analysis, freelancer, quiz_profile, weights, use_semantic
        )
        results.append(
            {
                "project_id": project.pk,
                "name": project.name,
                "description": project.description,
                "deadline": project.deadline,
                "estimated_amount": project.estimated_amount,
                "budget_min": analysis.get("budget_min"),
                "budget_max": analysis.get("budget_max"),
                "duree_semaines": analysis.get("duree_semaines"),
                "required_specialities": [
                    {
                        "nom": item.get("nom"),
                        "niveau": item.get("niveau"),
                        "nb": item.get("nb"),
                    }
                    for item in (analysis.get("specialites") or [])
                    if isinstance(item, dict)
                ],
                "match": scored,
            }
        )
    results.sort(
        key=lambda item: (-item["match"]["total_score"], item["project_id"])
    )
    return results[:limit] if limit else results
