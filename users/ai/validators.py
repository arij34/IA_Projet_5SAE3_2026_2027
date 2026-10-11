"""Validation des réponses du LLM pour la modération de profils."""

import json
from typing import Any

from .exceptions import LLMResponseError

_ALLOWED_STATUSES = frozenset({"OK", "SUSPECT", "REJETE"})
_CRITERIA_IDS = (
    "paiement_hors_plateforme",
    "promesses_irrealistes",
    "spam_incoherence",
    "contenu_interdit",
    "profil_trop_pauvre",
)
_REQUIRED_KEYS = frozenset({"statut", "raison", "confiance"})


def parse_moderation_response(raw_text: str) -> dict[str, Any]:
    """Extrait et valide la réponse JSON de modération du LLM.

    Args:
        raw_text: Réponse brute renvoyée par le LLM, éventuellement entourée
            d'une clôture Markdown `````json```.

    Returns:
        Le dictionnaire de modération validé.

    Raises:
        LLMResponseError: Si la réponse n'est pas un JSON conforme au schéma
            de modération attendu.
    """
    if not isinstance(raw_text, str):
        raise LLMResponseError("La réponse de modération doit être du texte.")

    response = _extract_json_object(raw_text)

    if not isinstance(response, dict):
        raise LLMResponseError("La réponse de modération doit être un objet JSON.")
    if not _REQUIRED_KEYS.issubset(response):
        raise LLMResponseError("Le schéma JSON de modération est invalide.")

    status = response["statut"]
    reason = response["raison"]
    confidence = response["confiance"]
    if not isinstance(status, str) or status.strip().upper() not in _ALLOWED_STATUSES:
        raise LLMResponseError("Le statut de modération est invalide.")
    if not isinstance(reason, str) or not reason.strip():
        raise LLMResponseError("La raison de modération doit être un texte non vide.")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise LLMResponseError("La confiance doit être un nombre entre 0 et 1.")

    return {
        "statut": status.strip().upper(),
        "raison": reason.strip(),
        "confiance": float(confidence),
        "criteres": _parse_criteria(response.get("criteres")),
    }


def _parse_criteria(value: Any) -> list[dict[str, Any]]:
    """Conserve les critères valides sans invalider une analyse."""
    if not isinstance(value, list):
        return []

    criteria = []
    for item in value:
        if not isinstance(item, dict):
            continue
        criterion_id = item.get("id")
        problem = item.get("probleme")
        comment = item.get("commentaire")
        if (
            criterion_id not in _CRITERIA_IDS
            or not isinstance(problem, bool)
            or not isinstance(comment, str)
        ):
            continue
        criteria.append(
            {
                "id": criterion_id,
                "probleme": problem,
                "commentaire": comment[:200],
            }
        )
        if len(criteria) == 5:
            break
    return criteria


def _extract_json_object(raw_text: str) -> Any:
    """Extrait le premier objet JSON présent dans un texte."""
    decoder = json.JSONDecoder()
    stripped_text = raw_text.strip()
    if stripped_text.startswith(("{", "[")):
        try:
            response, _ = decoder.raw_decode(stripped_text)
        except (json.JSONDecodeError, ValueError):
            pass
        else:
            return response

    for position, character in enumerate(raw_text):
        if character != "{":
            continue
        try:
            response, _ = decoder.raw_decode(raw_text[position:])
        except (json.JSONDecodeError, ValueError):
            continue
        return response
    raise LLMResponseError("La réponse de modération n'est pas un JSON valide.")
