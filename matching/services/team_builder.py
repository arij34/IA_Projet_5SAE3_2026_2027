"""Composition automatique d'équipe à partir des spécialités du projet.

Algorithme déterministe et glouton : les postes sont traités dans l'ordre des
spécialités de l'analyse, chaque poste prend le meilleur candidat encore
disponible, et un freelance n'occupe jamais deux postes.

Trois notions distinctes sont restituées, volontairement séparées :

- ``assigned_positions`` : postes auxquels un candidat a été attribué ;
- ``skill_covered_positions`` : postes dont le titulaire couvre réellement les
  compétences de la spécialité ;
- ``uncovered`` : postes sans titulaire, avec le motif et le meilleur candidat
  écarté.

Hypothèses de coût, explicites et configurables : un poste représente
``duree_semaines x heures_par_semaine x engagement`` heures, et son coût vaut
ce volume horaire multiplié par le tarif horaire du freelance. Le coût obtenu
est un montant total en euros, comparé au budget total du projet, également en
euros. Aucun budget horaire n'intervient dans cette comparaison.
"""

from ..constants import (
    ALGORITHM_VERSION,
    DEFAULT_ENGAGEMENT_RATIO,
    DEFAULT_HOURS_PER_WEEK,
    DEFAULT_TEAM_MIN_SCORE,
    DEFAULT_TEAM_MIN_SKILL_SCORE,
)
from .engine import eligible_freelancers
from .quiz_scoring import load_quiz_profiles
from .scoring import _setting, score_speciality


def get_min_score() -> float:
    """Seuil de compatibilité globale requis pour attribuer un poste."""
    return _setting("MATCHING_TEAM_MIN_SCORE", DEFAULT_TEAM_MIN_SCORE)


def get_min_skill_score() -> float:
    """Seuil du sous-score compétences pour déclarer un poste couvert."""
    return _setting("MATCHING_TEAM_MIN_SKILL_SCORE", DEFAULT_TEAM_MIN_SKILL_SCORE)


def hours_per_position(analysis: dict) -> float | None:
    """Volume horaire supposé d'un poste, sur toute la durée du projet."""
    try:
        weeks = float(analysis.get("duree_semaines") or 0)
    except (TypeError, ValueError):
        return None
    if weeks <= 0:
        return None
    hours = (
        weeks
        * _setting("MATCHING_HOURS_PER_WEEK", DEFAULT_HOURS_PER_WEEK)
        * _setting("MATCHING_ENGAGEMENT_RATIO", DEFAULT_ENGAGEMENT_RATIO)
    )
    return hours if hours > 0 else None


def _position_cost(analysis: dict, hourly_rate) -> float | None:
    """Coût total d'un poste : tarif horaire multiplié par le volume horaire."""
    if hourly_rate is None:
        return None
    try:
        rate = float(hourly_rate)
    except (TypeError, ValueError):
        return None
    hours = hours_per_position(analysis)
    if hours is None:
        return None
    return round(rate * hours, 2)


def _budget_total(analysis: dict, project) -> tuple[float | None, str]:
    """Budget total du projet et provenance de la valeur retenue."""
    for key in ("budget_recommande", "budget_max"):
        value = analysis.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number, key
    try:
        return float(project.estimated_amount), "montant_estime_projet"
    except (TypeError, ValueError):
        return None, "indisponible"


def _candidate_summary(entry: dict, analysis: dict, min_skill_score: float) -> dict:
    """Décrit un candidat évalué, qu'il soit retenu ou écarté."""
    freelancer = entry["freelancer"]
    skills = entry["subscores"].get("skills", {})
    skill_score = skills.get("score")
    return {
        "freelancer_id": freelancer.pk,
        "username": freelancer.username,
        "title": freelancer.title,
        "hourly_rate": (
            float(freelancer.hourly_rate)
            if freelancer.hourly_rate is not None
            else None
        ),
        "score": entry["deterministic_score"],
        "skill_score": skill_score,
        "skill_covered": skill_score is not None and skill_score >= min_skill_score,
        "missing_skills": list(skills.get("missing") or []),
        "matched_skills": list(skills.get("matched") or []),
        "estimated_cost": _position_cost(analysis, freelancer.hourly_rate),
        "justification": skills.get("detail", ""),
    }


def build_team(project, analysis: dict) -> dict:
    """Compose une équipe couvrant les spécialités requises par le projet."""
    min_score = get_min_score()
    min_skill_score = get_min_skill_score()

    specialities = [
        item
        for item in (analysis.get("specialites") or [])
        if isinstance(item, dict) and item.get("nom")
    ]
    candidates = list(eligible_freelancers())
    quiz_profiles = load_quiz_profiles(candidates)

    assigned_ids: set[int] = set()
    members: list[dict] = []
    uncovered: list[dict] = []

    for speciality in specialities:
        try:
            needed = int(speciality.get("nb", 1) or 1)
        except (TypeError, ValueError):
            needed = 1

        ranked = sorted(
            (
                score_speciality(
                    analysis,
                    speciality,
                    freelancer,
                    quiz_profiles.get(freelancer.pk, {}),
                )
                | {"freelancer": freelancer}
                for freelancer in candidates
                if freelancer.pk not in assigned_ids
            ),
            key=lambda item: (
                -item["deterministic_score"],
                item["freelancer"].pk,
            ),
        )

        assigned = 0
        rejected: list[dict] = []
        for entry in ranked:
            if assigned >= needed:
                break
            summary = _candidate_summary(entry, analysis, min_skill_score)
            if summary["score"] < min_score:
                rejected.append(summary)
                continue
            assigned_ids.add(summary["freelancer_id"])
            members.append(
                {
                    "speciality": speciality.get("nom"),
                    "required_level": str(speciality.get("niveau", "") or "").upper()
                    or None,
                    **summary,
                }
            )
            assigned += 1

        if assigned < needed:
            best_rejected = rejected[0] if rejected else None
            if not ranked:
                reason = "aucun_candidat_disponible"
            elif best_rejected is not None:
                reason = "aucun_candidat_suffisamment_compatible"
            else:
                reason = "candidats_insuffisants_en_nombre"
            uncovered.append(
                {
                    "speciality": speciality.get("nom"),
                    "required": needed,
                    "assigned": assigned,
                    "missing": needed - assigned,
                    "reason": reason,
                    "best_candidate": best_rejected,
                }
            )

    known_costs = [
        member["estimated_cost"]
        for member in members
        if member["estimated_cost"] is not None
    ]
    estimated_cost = round(sum(known_costs), 2) if known_costs else None
    unknown_costs = len(members) - len(known_costs)
    budget_total, budget_source = _budget_total(analysis, project)
    over_budget = (
        estimated_cost is not None
        and budget_total is not None
        and estimated_cost > budget_total
    )

    required_positions = sum(int(item.get("nb", 1) or 1) for item in specialities)
    skill_covered = sum(1 for member in members if member["skill_covered"])
    fully_staffed = required_positions > 0 and not uncovered
    fully_covered = fully_staffed and skill_covered == required_positions

    alerts: list[str] = []
    if required_positions == 0:
        alerts.append(
            "L'analyse du projet ne décrit aucune spécialité à pourvoir."
        )
    for item in uncovered:
        if item["reason"] == "aucun_candidat_suffisamment_compatible":
            alerts.append(
                f"Aucun candidat suffisamment compatible pour « {item['speciality']} » : "
                f"le meilleur profil atteint {item['best_candidate']['score']:.0f}/100 "
                f"pour un seuil de {min_score:.0f}/100."
            )
        elif item["reason"] == "aucun_candidat_disponible":
            alerts.append(
                f"Aucun freelance validé disponible pour « {item['speciality']} »."
            )
        else:
            alerts.append(
                f"Postes insuffisamment pourvus pour « {item['speciality']} » : "
                f"{item['assigned']} sur {item['required']}."
            )
    if fully_staffed and not fully_covered:
        alerts.append(
            "Tous les postes sont attribués, mais certains titulaires ne couvrent "
            "pas les compétences de leur spécialité."
        )
    if over_budget:
        alerts.append(
            "Le coût estimé de l'équipe dépasse le budget de référence du projet."
        )
    if unknown_costs:
        alerts.append(
            f"{unknown_costs} membre(s) sans tarif horaire : coût partiellement estimé."
        )

    return {
        "fully_staffed": fully_staffed,
        "fully_covered": fully_covered,
        "required_positions": required_positions,
        "assigned_positions": len(members),
        "skill_covered_positions": skill_covered,
        "members": members,
        "uncovered": uncovered,
        "estimated_cost": estimated_cost,
        "estimated_cost_partial": bool(unknown_costs),
        "budget_total": budget_total,
        "budget_source": budget_source,
        "over_budget": over_budget,
        "alerts": alerts,
        "assumptions": {
            "duree_semaines": analysis.get("duree_semaines"),
            "heures_par_semaine": _setting(
                "MATCHING_HOURS_PER_WEEK", DEFAULT_HOURS_PER_WEEK
            ),
            "taux_engagement": _setting(
                "MATCHING_ENGAGEMENT_RATIO", DEFAULT_ENGAGEMENT_RATIO
            ),
            "heures_par_poste": hours_per_position(analysis),
            "score_minimal": min_score,
            "score_competences_minimal": min_skill_score,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
