"""Validation défensive des réponses d'analyse de projet."""

import json
import math
from typing import Any

from .exceptions import LLMResponseError


MAX_ITEMS = 50
MAX_ITEM_CHARS = 500

_FIELDS = (
    "budget_min",
    "budget_max",
    "devise",
    "nb_freelancers",
    "specialites",
    "duree_semaines",
    "complexite",
    "risques",
    "jalons",
    "coherence_budget",
    "recommandation",
    "confiance",
)
_FIELD_SET = frozenset(_FIELDS)
_COMPLEXITIES = frozenset({"FAIBLE", "MOYENNE", "ELEVEE"})
_BUDGET_COHERENCES = frozenset({"SOUS_ESTIME", "COHERENT", "SUR_ESTIME"})


def parse_analysis_response(raw_text: str) -> dict:
    """Extrait, normalise et valide une analyse JSON renvoyée par le LLM."""
    try:
        payload = _extract_json_object(raw_text)
        _validate_payload(payload)
        return {field: payload[field] for field in _FIELDS}
    except LLMResponseError:
        raise
    except (
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
        json.JSONDecodeError,
    ):
        raise LLMResponseError("Réponse d'analyse invalide.") from None


def _extract_json_object(raw_text: str) -> dict:
    """Extrait un unique objet JSON, même entouré de texte ou de Markdown."""
    if not isinstance(raw_text, str):
        raise LLMResponseError("Réponse d'analyse invalide.")

    decoder = json.JSONDecoder(parse_constant=_reject_non_finite_constant)
    first_payload = None
    first_end = 0
    for position, character in enumerate(raw_text):
        if character != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(raw_text[position:])
        except (TypeError, ValueError, OverflowError, RecursionError):
            continue
        if not isinstance(candidate, dict):
            continue
        first_payload = candidate
        first_end = position + end
        break

    if first_payload is None:
        raise LLMResponseError("Réponse d'analyse invalide.")

    trailing_text = raw_text[first_end:]
    for position, character in enumerate(trailing_text):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(trailing_text[position:])
        except (TypeError, ValueError, OverflowError, RecursionError):
            continue
        if isinstance(candidate, dict):
            raise LLMResponseError("Réponse d'analyse invalide.")
    return first_payload


def _reject_non_finite_constant(value: str) -> Any:
    """Refuse les constantes JSON non finies."""
    raise ValueError(value)


def _validate_payload(payload: dict) -> None:
    """Vérifie les types, les bornes et normalise les valeurs textuelles."""
    if not _FIELD_SET.issubset(payload):
        raise LLMResponseError("Réponse d'analyse invalide.")

    payload["budget_min"] = _finite_number(payload["budget_min"], minimum=0)
    payload["budget_max"] = _finite_number(payload["budget_max"], minimum=0)
    if payload["budget_min"] > payload["budget_max"]:
        raise LLMResponseError("Réponse d'analyse invalide.")

    payload["devise"] = _bounded_string(payload["devise"])
    _bounded_integer(payload["nb_freelancers"], minimum=1, maximum=50)
    _validate_specialities(payload["specialites"])
    _bounded_integer(payload["duree_semaines"], minimum=1, maximum=520)
    payload["complexite"] = _bounded_choice(
        payload["complexite"],
        _COMPLEXITIES,
    )
    payload["risques"] = _validate_string_list(
        payload["risques"],
        minimum=1,
        maximum=5,
    )
    payload["jalons"] = _validate_string_list(
        payload["jalons"],
        minimum=2,
        maximum=6,
    )
    payload["coherence_budget"] = _bounded_choice(
        payload["coherence_budget"],
        _BUDGET_COHERENCES,
    )
    payload["recommandation"] = _bounded_string(payload["recommandation"])
    _finite_number(payload["confiance"], minimum=0, maximum=1)


def _finite_number(
    value: Any,
    minimum: float | None = None,
    maximum: float | None = None,
) -> int | float:
    """Valide un nombre fini qui n'est pas un booléen."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMResponseError("Réponse d'analyse invalide.")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise LLMResponseError("Réponse d'analyse invalide.")
    if minimum is not None and numeric_value < minimum:
        raise LLMResponseError("Réponse d'analyse invalide.")
    if maximum is not None and numeric_value > maximum:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return value


def _bounded_integer(value: Any, minimum: int, maximum: int) -> None:
    """Valide un entier hors booléen dans un intervalle fermé."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise LLMResponseError("Réponse d'analyse invalide.")
    if value < minimum or value > maximum:
        raise LLMResponseError("Réponse d'analyse invalide.")


def _bounded_string(value: Any) -> str:
    """Retourne une chaîne dépourvue d'espaces périphériques et bornée."""
    if not isinstance(value, str):
        raise LLMResponseError("Réponse d'analyse invalide.")
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_ITEM_CHARS:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return normalized


def _bounded_choice(value: Any, choices: frozenset[str]) -> str:
    """Normalise une valeur textuelle insensible à la casse."""
    normalized = _bounded_string(value).upper()
    if normalized not in choices:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return normalized


def _validate_string_list(value: Any, minimum: int, maximum: int) -> list[str]:
    """Valide et normalise une liste bornée de chaînes."""
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise LLMResponseError("Réponse d'analyse invalide.")
    return [_bounded_string(item) for item in value]


def _validate_specialities(value: Any) -> None:
    """Valide les noms et effectifs des spécialités demandées."""
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise LLMResponseError("Réponse d'analyse invalide.")
    for speciality in value:
        if not isinstance(speciality, dict) or not {"nom", "nb"} <= speciality.keys():
            raise LLMResponseError("Réponse d'analyse invalide.")
        speciality["nom"] = _bounded_string(speciality["nom"])
        _bounded_integer(speciality["nb"], minimum=1, maximum=50)
