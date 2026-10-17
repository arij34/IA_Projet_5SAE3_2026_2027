"""Moteur de matching déterministe, reproductible et explicable.

Le moteur ne lit que des données déjà produites par les modules users,
projects et challenges. Il n'écrit dans aucun de ces modules.
"""

import math

from django.conf import settings

from ..constants import (
    ALGORITHM_VERSION,
    DEFAULT_BUDGET_TOLERANCE,
    DEFAULT_ENGAGEMENT_RATIO,
    DEFAULT_HOURS_PER_WEEK,
    DEFAULT_QUIZ_INDIRECT_FACTOR,
    DEFAULT_WEIGHTS,
    LEVELS,
    LEVEL_GAP_SCORES,
    MAX_SCORE,
    MIN_SCORE,
    QUIZ_LEVEL_THRESHOLDS,
    RATE_LEVEL_THRESHOLDS,
)
from .quiz_scoring import speciality_quiz_score
from .text import overlap_ratio, tokenize, tokenize_all


def get_weights() -> dict[str, float]:
    """Retourne les poids configurés, complétés par les valeurs par défaut."""
    configured = getattr(settings, "MATCHING_WEIGHTS", None) or {}
    weights = dict(DEFAULT_WEIGHTS)
    for key, value in configured.items():
        if key in weights:
            try:
                weights[key] = float(value)
            except (TypeError, ValueError):
                continue
    return weights


def _setting(name: str, default: float) -> float:
    """Lit un réglage numérique du matching avec repli sur sa valeur par défaut."""
    try:
        return float(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    """Borne une valeur dans l'intervalle de score autorisé."""
    return max(MIN_SCORE, min(MAX_SCORE, value))


# --- Sous-score 1 : compétences --------------------------------------------


def skills_subscore(speciality: dict, freelancer_skills) -> dict:
    """Compare les compétences requises aux compétences déclarées."""
    required_tokens = tokenize(speciality.get("nom", ""))
    available_tokens = tokenize_all(freelancer_skills)
    if not required_tokens:
        return {
            "available": False,
            "score": None,
            "detail": "Spécialité sans libellé exploitable.",
            "matched": [],
            "missing": [],
        }
    if not available_tokens:
        return {
            "available": True,
            "score": MIN_SCORE,
            "detail": "Aucune compétence déclarée par le freelance.",
            "matched": [],
            "missing": sorted(required_tokens),
        }
    matched = sorted(required_tokens & available_tokens)
    missing = sorted(required_tokens - available_tokens)
    ratio = overlap_ratio(required_tokens, available_tokens)
    return {
        "available": True,
        "score": _clamp(ratio * MAX_SCORE),
        "detail": (
            f"{len(matched)} terme(s) de la spécialité sur {len(required_tokens)} "
            "couverts par les compétences déclarées."
        ),
        "matched": matched,
        "missing": missing,
    }


# --- Sous-score 2 : budget --------------------------------------------------


def _budget_reference(analysis: dict) -> float | None:
    """Retourne le budget de référence de l'analyse, si disponible."""
    for key in ("budget_recommande", "budget_max", "budget_min"):
        value = analysis.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def affordable_hourly_rate(analysis: dict, speciality: dict) -> float | None:
    """Estime le tarif horaire finançable pour un poste de la spécialité.

    Hypothèses documentées : le budget de référence est réparti selon la charge
    déclarée de la spécialité puis divisé par le nombre de postes ; le volume
    horaire d'un poste vaut duree_semaines x heures_par_semaine x engagement.
    """
    budget = _budget_reference(analysis)
    weeks = analysis.get("duree_semaines")
    if not budget or not weeks:
        return None
    try:
        weeks = float(weeks)
    except (TypeError, ValueError):
        return None
    if weeks <= 0:
        return None

    try:
        charge = float(speciality.get("charge_pourcentage", 0) or 0)
        count = int(speciality.get("nb", 1) or 1)
    except (TypeError, ValueError):
        return None
    if charge <= 0 or count <= 0:
        return None

    hours = (
        weeks
        * _setting("MATCHING_HOURS_PER_WEEK", DEFAULT_HOURS_PER_WEEK)
        * _setting("MATCHING_ENGAGEMENT_RATIO", DEFAULT_ENGAGEMENT_RATIO)
    )
    if hours <= 0:
        return None
    allocated = budget * (charge / 100.0) / count
    return allocated / hours


def budget_subscore(analysis: dict, speciality: dict, hourly_rate) -> dict:
    """Évalue la compatibilité entre le tarif du freelance et le budget."""
    if hourly_rate is None:
        return {
            "available": False,
            "score": None,
            "detail": "Tarif horaire non renseigné : critère neutralisé.",
            "affordable_rate": None,
            "hourly_rate": None,
        }
    try:
        rate = float(hourly_rate)
    except (TypeError, ValueError):
        return {
            "available": False,
            "score": None,
            "detail": "Tarif horaire illisible : critère neutralisé.",
            "affordable_rate": None,
            "hourly_rate": None,
        }

    affordable = affordable_hourly_rate(analysis, speciality)
    if affordable is None or affordable <= 0:
        return {
            "available": False,
            "score": None,
            "detail": "Budget ou durée absents de l'analyse : critère neutralisé.",
            "affordable_rate": None,
            "hourly_rate": round(rate, 2),
        }

    if rate <= affordable:
        return {
            "available": True,
            "score": MAX_SCORE,
            "detail": (
                f"Tarif de {rate:.2f} compatible avec le budget horaire "
                f"finançable de {affordable:.2f}."
            ),
            "affordable_rate": round(affordable, 2),
            "hourly_rate": round(rate, 2),
        }

    tolerance = _setting("MATCHING_BUDGET_TOLERANCE", DEFAULT_BUDGET_TOLERANCE)
    overrun = (rate - affordable) / affordable
    score = _clamp(MAX_SCORE * (1 - overrun / tolerance)) if tolerance > 0 else MIN_SCORE
    return {
        "available": True,
        "score": score,
        "detail": (
            f"Tarif de {rate:.2f} supérieur de {overrun * 100:.0f} % au budget "
            f"horaire finançable de {affordable:.2f}."
        ),
        "affordable_rate": round(affordable, 2),
        "hourly_rate": round(rate, 2),
    }


# --- Sous-score 3 : niveau --------------------------------------------------


def estimate_level(hourly_rate, quiz_profile: dict) -> dict:
    """Estime le niveau d'un freelance à partir des données disponibles."""
    average = (quiz_profile or {}).get("global_average")
    if average is not None:
        for threshold, level in QUIZ_LEVEL_THRESHOLDS:
            if average >= threshold:
                return {"level": level, "source": "quiz"}
        return {"level": "JUNIOR", "source": "quiz"}

    if hourly_rate is not None:
        try:
            rate = float(hourly_rate)
        except (TypeError, ValueError):
            rate = None
        if rate is not None:
            for threshold, level in RATE_LEVEL_THRESHOLDS:
                if rate >= threshold:
                    return {"level": level, "source": "tarif"}
            return {"level": "JUNIOR", "source": "tarif"}

    return {"level": None, "source": "indisponible"}


def level_subscore(speciality: dict, hourly_rate, quiz_profile: dict) -> dict:
    """Compare le niveau requis au niveau estimé du freelance."""
    required = str(speciality.get("niveau", "") or "").upper()
    estimated = estimate_level(hourly_rate, quiz_profile)
    if required not in LEVELS or estimated["level"] is None:
        return {
            "available": False,
            "score": None,
            "required_level": required or None,
            "estimated_level": estimated["level"],
            "estimation_source": estimated["source"],
            "detail": "Niveau requis ou niveau estimé indisponible.",
        }

    gap = LEVELS.index(estimated["level"]) - LEVELS.index(required)
    score = LEVEL_GAP_SCORES.get(gap, MIN_SCORE)
    return {
        "available": True,
        "score": float(score),
        "required_level": required,
        "estimated_level": estimated["level"],
        "estimation_source": estimated["source"],
        "detail": (
            f"Niveau estimé {estimated['level']} pour un besoin {required}, "
            f"source {estimated['source']}."
        ),
    }


# --- Agrégation -------------------------------------------------------------


def aggregate(subscores: dict, weights: dict) -> dict:
    """Agrège les sous-scores disponibles en renormalisant leurs poids."""
    available = {
        key: value
        for key, value in subscores.items()
        if value.get("available") and value.get("score") is not None
    }
    total_weight = sum(weights.get(key, 0.0) for key in available)
    if total_weight <= 0:
        return {
            "score": MIN_SCORE,
            "applied_weights": {},
            "skipped": sorted(set(subscores) - set(available)),
        }

    applied = {key: weights.get(key, 0.0) / total_weight for key in available}
    score = sum(available[key]["score"] * applied[key] for key in available)
    return {
        "score": round(_clamp(score), 2),
        "applied_weights": {key: round(value, 4) for key, value in applied.items()},
        "skipped": sorted(set(subscores) - set(available)),
    }


def score_speciality(
    analysis: dict,
    speciality: dict,
    freelancer,
    quiz_profile: dict,
    weights: dict | None = None,
) -> dict:
    """Calcule le score déterministe d'un freelance pour une spécialité."""
    weights = weights or get_weights()
    indirect_factor = _setting(
        "MATCHING_QUIZ_INDIRECT_FACTOR", DEFAULT_QUIZ_INDIRECT_FACTOR
    )
    subscores = {
        "skills": skills_subscore(speciality, getattr(freelancer, "skills", None)),
        "budget": budget_subscore(
            analysis, speciality, getattr(freelancer, "hourly_rate", None)
        ),
        "level": level_subscore(
            speciality, getattr(freelancer, "hourly_rate", None), quiz_profile
        ),
        "quiz": speciality_quiz_score(
            quiz_profile, [speciality.get("nom", "")], indirect_factor
        ),
    }
    for value in subscores.values():
        if value.get("score") is not None:
            value["score"] = round(float(value["score"]), 2)

    aggregated = aggregate(subscores, weights)
    return {
        "speciality": speciality.get("nom", ""),
        "required_level": str(speciality.get("niveau", "") or "").upper() or None,
        "required_count": speciality.get("nb"),
        "deterministic_score": aggregated["score"],
        "subscores": subscores,
        "applied_weights": aggregated["applied_weights"],
        "skipped_criteria": aggregated["skipped"],
        "algorithm_version": ALGORITHM_VERSION,
    }


def best_speciality_score(
    analysis: dict,
    freelancer,
    quiz_profile: dict,
    weights: dict | None = None,
) -> dict:
    """Retourne le meilleur score du freelance parmi les spécialités du projet."""
    specialities = analysis.get("specialites") or []
    results = [
        score_speciality(analysis, speciality, freelancer, quiz_profile, weights)
        for speciality in specialities
        if isinstance(speciality, dict)
    ]
    if not results:
        return {
            "speciality": "",
            "required_level": None,
            "required_count": None,
            "deterministic_score": MIN_SCORE,
            "subscores": {},
            "applied_weights": {},
            "skipped_criteria": [],
            "algorithm_version": ALGORITHM_VERSION,
            "all_specialities": [],
        }
    best = dict(max(results, key=lambda item: item["deterministic_score"]))
    best["all_specialities"] = [
        {"speciality": item["speciality"], "score": item["deterministic_score"]}
        for item in results
    ]
    return best


def _display_score(value: float) -> int:
    """Arrondit un score à l'entier le plus proche, moitié vers le haut.

    L'arrondi par défaut de Python est au pair le plus proche : il afficherait
    72 pour 72.5 alors que l'interface affiche 73. Cette fonction garantit la
    cohérence entre les explications et les barres de score.
    """
    return int(math.floor(float(value) + 0.5))


def explain(result: dict) -> list:
    """Produit des explications lisibles et vérifiables du score."""
    lines = []
    subscores = result.get("subscores") or {}
    labels = {
        "skills": "Compétences",
        "budget": "Budget",
        "level": "Niveau",
        "quiz": "Quiz",
    }
    for key, label in labels.items():
        value = subscores.get(key)
        if not value:
            continue
        if value.get("available") and value.get("score") is not None:
            lines.append(
                f"{label} : {_display_score(value['score'])}/100. {value['detail']}"
            )
        else:
            lines.append(f"{label} : non évalué. {value.get('detail', '')}".strip())
    return lines
