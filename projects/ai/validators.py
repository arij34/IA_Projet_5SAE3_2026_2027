"""Validation défensive des évaluations détaillées de projets."""

import json
import math
from typing import Any

from .exceptions import LLMResponseError


MIN_SCORE_COMPLEXITY = 1
MAX_SCORE_COMPLEXITY = 10
MIN_DURATION_WEEKS = 1
MAX_DURATION_WEEKS = 520
MIN_TEAM_SIZE = 1
MAX_TEAM_SIZE = 50
MIN_PHASES = 3
MAX_PHASES = 8
MIN_MILESTONES = 2
MAX_MILESTONES = 8
MIN_RISKS = 1
MAX_RISKS = 10
MAX_LIST_ITEMS = 50
MAX_ITEM_CHARS = 500
MIN_PERCENTAGE = 0
MAX_PERCENTAGE = 100
PERCENTAGE_TOLERANCE = 0.01
DURATION_TOLERANCE_WEEKS = 1
MIN_PROBABILITY = 0
MAX_PROBABILITY = 1

_FIELDS = (
    "budget_min", "budget_max", "devise", "nb_freelancers", "specialites",
    "duree_semaines", "complexite", "risques", "jalons", "coherence_budget",
    "recommandation", "confiance", "score_complexite", "facteurs_complexite",
    "duree_min_semaines", "duree_max_semaines", "budget_recommande",
    "justification", "phases", "faisabilite_deadline",
    "faisabilite_deadline_justification", "taux_reussite",
    "facteurs_positifs", "facteurs_negatifs", "hypotheses",
    "questions_clarification", "recommandations",
)
_FIELD_SET = frozenset(_FIELDS)
_COMPLEXITIES = frozenset({"FAIBLE", "MOYENNE", "ELEVEE", "TRES_ELEVEE"})
_BUDGET_COHERENCES = frozenset({"SOUS_ESTIME", "REALISTE", "SUR_ESTIME"})
_FEASIBILITIES = frozenset({"TENABLE", "SERREE", "IRREALISTE"})
_LEVELS = frozenset({"JUNIOR", "CONFIRME", "SENIOR"})


def parse_analysis_response(raw_text: str) -> dict:
    """Extrait, normalise et valide une évaluation complète."""
    try:
        payload = _extract_json_object(raw_text)
        _validate_payload(payload)
        return {field: payload[field] for field in _FIELDS}
    except LLMResponseError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise LLMResponseError("Réponse d'analyse invalide.") from None


def _extract_json_object(raw_text: str) -> dict:
    """Extrait un unique objet JSON, éventuellement entouré de texte."""
    if not isinstance(raw_text, str):
        raise LLMResponseError("Réponse d'analyse invalide.")
    decoder = json.JSONDecoder(parse_constant=_reject_non_finite_constant)
    found = None
    end_position = 0
    for position, character in enumerate(raw_text):
        if character != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(raw_text[position:])
        except (TypeError, ValueError, OverflowError, RecursionError):
            continue
        if isinstance(candidate, dict):
            found = candidate
            end_position = position + end
            break
    if found is None:
        raise LLMResponseError("Réponse d'analyse invalide.")
    trailing = raw_text[end_position:]
    for position, character in enumerate(trailing):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(trailing[position:])
        except (TypeError, ValueError, OverflowError, RecursionError):
            continue
        if isinstance(candidate, dict):
            raise LLMResponseError("Réponse d'analyse invalide.")
    return found


def _reject_non_finite_constant(value: str) -> Any:
    """Refuse Infinity, NaN et les constantes JSON non finies."""
    raise ValueError(value)


def _validate_payload(payload: dict) -> None:
    """Vérifie le schéma, les bornes et les cohérences inter-champs."""
    if not _FIELD_SET.issubset(payload):
        raise LLMResponseError("Réponse d'analyse invalide.")
    payload["budget_min"] = _number(payload["budget_min"], minimum=0)
    payload["budget_max"] = _number(payload["budget_max"], minimum=0)
    payload["budget_recommande"] = _number(payload["budget_recommande"], minimum=0)
    if not payload["budget_min"] <= payload["budget_recommande"] <= payload["budget_max"]:
        raise LLMResponseError("Réponse d'analyse invalide.")
    payload["devise"] = _string(payload["devise"])
    _integer(payload["nb_freelancers"], MIN_TEAM_SIZE, MAX_TEAM_SIZE)
    speciality_names, speciality_total = _validate_specialities(payload["specialites"])
    if payload["nb_freelancers"] != speciality_total:
        raise LLMResponseError("Réponse d'analyse invalide.")
    payload["duree_semaines"] = _integer_value(
        payload["duree_semaines"], MIN_DURATION_WEEKS, MAX_DURATION_WEEKS
    )
    payload["duree_min_semaines"] = _integer_value(
        payload["duree_min_semaines"], MIN_DURATION_WEEKS, MAX_DURATION_WEEKS
    )
    payload["duree_max_semaines"] = _integer_value(
        payload["duree_max_semaines"], MIN_DURATION_WEEKS, MAX_DURATION_WEEKS
    )
    if not payload["duree_min_semaines"] <= payload["duree_semaines"] <= payload["duree_max_semaines"]:
        raise LLMResponseError("Réponse d'analyse invalide.")
    payload["complexite"] = _choice(payload["complexite"], _COMPLEXITIES)
    payload["coherence_budget"] = _choice(payload["coherence_budget"], _BUDGET_COHERENCES)
    payload["faisabilite_deadline"] = _choice(payload["faisabilite_deadline"], _FEASIBILITIES)
    payload["confiance"] = _number(payload["confiance"], MIN_PROBABILITY, MAX_PROBABILITY)
    payload["taux_reussite"] = _number(payload["taux_reussite"], MIN_PROBABILITY, MAX_PROBABILITY)
    _integer(payload["score_complexite"], MIN_SCORE_COMPLEXITY, MAX_SCORE_COMPLEXITY)
    payload["facteurs_complexite"] = _string_list(payload["facteurs_complexite"], 1, MAX_LIST_ITEMS)
    payload["risques"] = _validate_risks(payload["risques"])
    payload["jalons"] = _validate_milestones(payload["jalons"])
    payload["phases"] = _validate_phases(payload["phases"], speciality_names, payload["duree_semaines"])
    payload["facteurs_positifs"] = _string_list(payload["facteurs_positifs"], 0, MAX_LIST_ITEMS)
    payload["facteurs_negatifs"] = _string_list(payload["facteurs_negatifs"], 0, MAX_LIST_ITEMS)
    payload["hypotheses"] = _string_list(payload["hypotheses"], 0, MAX_LIST_ITEMS)
    payload["questions_clarification"] = _string_list(payload["questions_clarification"], 0, MAX_LIST_ITEMS)
    payload["recommandations"] = _string_list(payload["recommandations"], 1, MAX_LIST_ITEMS)
    payload["recommandation"] = _string(payload["recommandation"])
    payload["justification"] = _string(payload["justification"])
    payload["faisabilite_deadline_justification"] = _string(payload["faisabilite_deadline_justification"])


def _number(value: Any, minimum: float | None = None, maximum: float | None = None) -> int | float:
    """Valide un nombre fini qui n'est pas un booléen."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMResponseError("Réponse d'analyse invalide.")
    numeric = float(value)
    if not math.isfinite(numeric) or (minimum is not None and numeric < minimum) or (
        maximum is not None and numeric > maximum
    ):
        raise LLMResponseError("Réponse d'analyse invalide.")
    return value


def _integer(value: Any, minimum: int, maximum: int) -> None:
    """Valide un entier borné sans accepter les booléens."""
    _integer_value(value, minimum, maximum)


def _integer_value(value: Any, minimum: int, maximum: int) -> int:
    """Retourne un entier borné sans accepter les booléens."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return value


def _string(value: Any) -> str:
    """Normalise une chaîne non vide et bornée."""
    if not isinstance(value, str):
        raise LLMResponseError("Réponse d'analyse invalide.")
    value = value.strip()
    if not value or len(value) > MAX_ITEM_CHARS:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return value


def _choice(value: Any, choices: frozenset[str]) -> str:
    """Normalise une énumération insensible à la casse."""
    normalized = _string(value).upper()
    if normalized not in choices:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return normalized


def _string_list(value: Any, minimum: int, maximum: int) -> list[str]:
    """Valide une liste bornée de chaînes."""
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return [_string(item) for item in value]


def _validate_specialities(value: Any) -> tuple[set[str], int]:
    """Valide les spécialités, leurs niveaux et leurs charges."""
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_LIST_ITEMS:
        raise LLMResponseError("Réponse d'analyse invalide.")
    names: set[str] = set()
    total = 0
    for speciality in value:
        if not isinstance(speciality, dict) or not {"nom", "nb", "niveau", "charge_pourcentage"} <= speciality.keys():
            raise LLMResponseError("Réponse d'analyse invalide.")
        speciality["nom"] = _string(speciality["nom"])
        names.add(speciality["nom"])
        speciality["niveau"] = _choice(speciality["niveau"], _LEVELS)
        speciality["nb"] = _integer_value(speciality["nb"], MIN_TEAM_SIZE, MAX_TEAM_SIZE)
        speciality["charge_pourcentage"] = _number(
            speciality["charge_pourcentage"], MIN_PERCENTAGE, MAX_PERCENTAGE
        )
        total += speciality["nb"]
    if not math.isclose(
        sum(item["charge_pourcentage"] for item in value),
        MAX_PERCENTAGE,
        abs_tol=PERCENTAGE_TOLERANCE,
    ):
        raise LLMResponseError("Réponse d'analyse invalide.")
    return names, total


def _validate_risks(value: Any) -> list[dict]:
    """Valide les risques structurés."""
    if not isinstance(value, list) or not MIN_RISKS <= len(value) <= MAX_RISKS:
        raise LLMResponseError("Réponse d'analyse invalide.")
    for risk in value:
        if not isinstance(risk, dict) or not {"description", "probabilite", "impact", "mitigation"} <= risk.keys():
            raise LLMResponseError("Réponse d'analyse invalide.")
        risk["description"] = _string(risk["description"])
        risk["impact"] = _string(risk["impact"])
        risk["mitigation"] = _string(risk["mitigation"])
        risk["probabilite"] = _number(risk["probabilite"], MIN_PROBABILITY, MAX_PROBABILITY)
    return value


def _validate_milestones(value: Any) -> list[dict]:
    """Valide les jalons et leurs semaines."""
    if not isinstance(value, list) or not MIN_MILESTONES <= len(value) <= MAX_MILESTONES:
        raise LLMResponseError("Réponse d'analyse invalide.")
    for milestone in value:
        if not isinstance(milestone, dict) or not {"nom", "semaine"} <= milestone.keys():
            raise LLMResponseError("Réponse d'analyse invalide.")
        milestone["nom"] = _string(milestone["nom"])
        milestone["semaine"] = _integer_value(milestone["semaine"], MIN_DURATION_WEEKS, MAX_DURATION_WEEKS)
    return value


def _validate_phases(value: Any, speciality_names: set[str], total_duration: int) -> list[dict]:
    """Valide les phases, leurs spécialités et leurs cohérences."""
    if not isinstance(value, list) or not MIN_PHASES <= len(value) <= MAX_PHASES:
        raise LLMResponseError("Réponse d'analyse invalide.")
    duration_total = 0
    percentage_total = 0.0
    for phase in value:
        required = {"nom", "objectif", "duree_semaines", "livrables", "specialites", "budget_pourcentage"}
        if not isinstance(phase, dict) or not required <= phase.keys():
            raise LLMResponseError("Réponse d'analyse invalide.")
        phase["nom"] = _string(phase["nom"])
        phase["objectif"] = _string(phase["objectif"])
        phase["duree_semaines"] = _integer_value(
            phase["duree_semaines"], MIN_DURATION_WEEKS, MAX_DURATION_WEEKS
        )
        phase["livrables"] = _string_list(phase["livrables"], 1, MAX_LIST_ITEMS)
        phase["specialites"] = _string_list(phase["specialites"], 1, MAX_LIST_ITEMS)
        if not set(phase["specialites"]) <= speciality_names:
            raise LLMResponseError("Réponse d'analyse invalide.")
        phase["budget_pourcentage"] = _number(
            phase["budget_pourcentage"], MIN_PERCENTAGE, MAX_PERCENTAGE
        )
        duration_total += phase["duree_semaines"]
        percentage_total += phase["budget_pourcentage"]
    if not math.isclose(percentage_total, MAX_PERCENTAGE, abs_tol=PERCENTAGE_TOLERANCE):
        raise LLMResponseError("Réponse d'analyse invalide.")
    if abs(duration_total - total_duration) > DURATION_TOLERANCE_WEEKS:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return value
