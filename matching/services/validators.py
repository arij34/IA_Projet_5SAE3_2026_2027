"""Validation stricte des réponses JSON du matching sémantique.

Le schéma est volontairement fermé : tout champ inconnu, toute valeur hors
plage ou tout type inattendu provoque un rejet. Aucune donnée issue du LLM
n'est utilisée avant d'avoir traversé ce module.
"""

import json

from projects.ai.exceptions import LLMResponseError

MIN_SEMANTIC_SCORE = 0.0
MAX_SEMANTIC_SCORE = 100.0
MAX_LIST_ITEMS = 12
MAX_ITEM_CHARS = 120
MAX_JUSTIFICATION_CHARS = 400

REQUIRED_FIELDS = frozenset({"score_semantique", "justification"})
ALLOWED_FIELDS = frozenset(
    {
        "score_semantique",
        "concepts_correspondants",
        "competences_pertinentes",
        "justification",
    }
)


def _string(value, max_chars: int) -> str:
    """Valide une chaîne non vide et bornée."""
    if not isinstance(value, str):
        raise LLMResponseError("Réponse de matching invalide.")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_chars:
        raise LLMResponseError("Réponse de matching invalide.")
    return cleaned


def _string_list(value) -> list:
    """Valide une liste bornée de chaînes courtes et distinctes."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
        raise LLMResponseError("Réponse de matching invalide.")
    items = []
    for entry in value:
        cleaned = _string(entry, MAX_ITEM_CHARS)
        if cleaned not in items:
            items.append(cleaned)
    return items


def _score(value) -> float:
    """Valide un score numérique compris entre 0 et 100."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMResponseError("Réponse de matching invalide.")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise LLMResponseError("Réponse de matching invalide.")
    if not MIN_SEMANTIC_SCORE <= number <= MAX_SEMANTIC_SCORE:
        raise LLMResponseError("Réponse de matching invalide.")
    return round(number, 2)


def parse_semantic_response(raw: str) -> dict:
    """Analyse et valide la réponse JSON du matching sémantique."""
    if not isinstance(raw, str) or not raw.strip():
        raise LLMResponseError("Réponse de matching absente.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise LLMResponseError("Réponse de matching non JSON.") from None

    if not isinstance(payload, dict):
        raise LLMResponseError("Réponse de matching invalide.")
    if not REQUIRED_FIELDS <= payload.keys():
        raise LLMResponseError("Réponse de matching incomplète.")
    if not payload.keys() <= ALLOWED_FIELDS:
        raise LLMResponseError("Réponse de matching contenant des champs inconnus.")

    return {
        "score_semantique": _score(payload["score_semantique"]),
        "concepts_correspondants": _string_list(
            payload.get("concepts_correspondants")
        ),
        "competences_pertinentes": _string_list(
            payload.get("competences_pertinentes")
        ),
        "justification": _string(
            payload["justification"], MAX_JUSTIFICATION_CHARS
        ),
    }
