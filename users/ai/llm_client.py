"""Client unique pour appeler le LLM depuis Django.

Fournisseurs (variable LLM_PROVIDER dans .env) :
- "mock"      : réponses simulées, sans clé API (développement et tests)
- "anthropic" : API Claude

Le LLM n'est jamais appelé depuis React : la clé reste côté serveur.
"""
import logging

import requests
from django.conf import settings

from .exceptions import (
    LLMConfigError,
    LLMQuotaError,
    LLMResponseError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_ATTEMPTS = 2  # 1 appel + 1 nouvel essai sur erreur temporaire


def call_llm(system_prompt: str, user_content: str, max_tokens: int = 500) -> str:
    """Envoie le prompt au LLM et retourne le texte brut de la réponse."""
    provider = getattr(settings, "LLM_PROVIDER", "mock")
    if provider == "mock":
        return _call_mock(system_prompt)
    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_content, max_tokens)
    raise LLMConfigError(f"Fournisseur LLM inconnu : {provider!r}")


def _call_mock(system_prompt: str) -> str:
    """Réponse simulée pour développer sans clé API."""
    if "statut" in system_prompt.lower():
        return '{"statut": "OK", "raison": "Réponse simulée (mode mock).", "confiance": 0.5}'
    return (
        '{"score": 60, "points_faibles": ["Bio trop courte (réponse simulée)"], '
        '"suggestions": ["Ajoutez vos réalisations principales (réponse simulée)"]}'
    )


def _call_anthropic(system_prompt: str, user_content: str, max_tokens: int) -> str:
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise LLMConfigError("ANTHROPIC_API_KEY est absente (vérifiez le fichier .env).")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": settings.LLM_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    timeout = settings.LLM_TIMEOUT_SECONDS

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                ANTHROPIC_URL, headers=headers, json=payload, timeout=timeout
            )
        except requests.Timeout:
            last_error = LLMTimeoutError("Le LLM n'a pas répondu à temps.")
            logger.warning("Timeout LLM (essai %s/%s)", attempt, MAX_ATTEMPTS)
            continue
        except requests.RequestException as exc:
            raise LLMResponseError(f"Erreur réseau vers le LLM : {exc}") from exc

        if response.status_code == 429:
            raise LLMQuotaError("Quota ou limite de requêtes dépassé.")
        if response.status_code in (401, 403):
            raise LLMConfigError("Clé API refusée par le fournisseur.")
        if response.status_code >= 500:
            last_error = LLMResponseError(f"Erreur serveur LLM ({response.status_code}).")
            logger.warning("Erreur %s du LLM (essai %s/%s)", response.status_code, attempt, MAX_ATTEMPTS)
            continue
        if response.status_code != 200:
            raise LLMResponseError(f"Réponse inattendue du LLM ({response.status_code}).")

        return _extract_text(response)

    raise last_error


def _extract_text(response: requests.Response) -> str:
    try:
        data = response.json()
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
    except (ValueError, AttributeError) as exc:
        raise LLMResponseError("Réponse du LLM illisible.") from exc
    if not text.strip():
        raise LLMResponseError("Réponse vide du LLM.")
    return text
