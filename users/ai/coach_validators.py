"""Validation des réponses du coach IA de profil freelancer."""

import math
from typing import Any

from .exceptions import LLMResponseError
from .validators import _extract_json_object

MAX_ITEM_CHARS = 200
MAX_ITEMS = 5

_REQUIRED_KEYS = frozenset(
    {"score", "points_forts", "points_faibles", "suggestions"}
)


def parse_coach_response(raw_text: str) -> dict[str, Any]:
    """Extrait et valide la réponse JSON du coach de profil.

    Args:
        raw_text: Réponse brute du LLM, éventuellement entourée de Markdown
            ou de texte explicatif.

    Returns:
        Un dictionnaire contenant exactement les quatre champs normalisés du
        coach.

    Raises:
        LLMResponseError: Si la réponse ne respecte pas le schéma attendu.
    """
    try:
        if not isinstance(raw_text, str):
            raise LLMResponseError("La réponse du coach doit être du texte.")

        response = _extract_json_object(raw_text)
        if not isinstance(response, dict):
            raise LLMResponseError("La réponse du coach doit être un objet JSON.")
        if not _REQUIRED_KEYS.issubset(response):
            raise LLMResponseError("Le schéma JSON du coach est invalide.")

        score = _parse_score(response["score"])
        points_forts = _parse_items(response["points_forts"], "points forts")
        points_faibles = _parse_items(response["points_faibles"], "points faibles")
        suggestions = _parse_items(response["suggestions"], "suggestions")
        if not suggestions:
            raise LLMResponseError("Les suggestions du coach ne peuvent pas être vides.")

        return {
            "score": score,
            "points_forts": points_forts,
            "points_faibles": points_faibles,
            "suggestions": suggestions,
        }
    except LLMResponseError:
        raise
    except (OverflowError, TypeError, ValueError) as exc:
        raise LLMResponseError("La réponse du coach est invalide.") from exc


def _parse_score(value: Any) -> int:
    """Valide un score numérique fini et le normalise en entier."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMResponseError("Le score du coach doit être un nombre.")
    if isinstance(value, float) and not math.isfinite(value):
        raise LLMResponseError("Le score du coach doit être un nombre fini.")
    if not 0 <= value <= 100:
        raise LLMResponseError("Le score du coach doit être compris entre 0 et 100.")
    return int(round(value))


def _parse_items(value: Any, field_name: str) -> list[str]:
    """Valide, normalise et limite une liste de textes du coach."""
    if not isinstance(value, list):
        raise LLMResponseError(f"Le champ {field_name} doit être une liste.")

    items = []
    for item in value[:MAX_ITEMS]:
        if not isinstance(item, str) or not item.strip():
            raise LLMResponseError(
                f"Chaque élément de {field_name} doit être un texte non vide."
            )
        items.append(item.strip()[:MAX_ITEM_CHARS])
    return items
