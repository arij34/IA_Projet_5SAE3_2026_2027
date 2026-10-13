"""Client Anthropic isolé pour les fonctionnalités IA de projects."""

import logging
from typing import Any

import requests
from django.conf import settings

from .exceptions import (
    LLMAuthError,
    LLMConfigError,
    LLMQuotaError,
    LLMResponseError,
    LLMServiceError,
    LLMTimeoutError,
)


logger = logging.getLogger(__name__)

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
REQUEST_TIMEOUT_SECONDS = 20
MAX_OUTPUT_TOKENS = 1024
MAX_ATTEMPTS = 2


def call_llm(system_prompt: str, user_text: str) -> str:
    """Envoie une requête au fournisseur configuré et retourne son texte."""
    provider = getattr(settings, "PROJECT_LLM_PROVIDER", "")
    if provider == "mock":
        from .simulator import simulate_analysis

        return simulate_analysis(user_text)
    if provider != "anthropic":
        raise LLMConfigError("Le fournisseur LLM projects est invalide.")

    api_key = getattr(settings, "PROJECT_LLM_API_KEY", "")
    model = getattr(settings, "PROJECT_LLM_MODEL", "")
    if not api_key or not model:
        raise LLMConfigError("La configuration du fournisseur LLM est incomplète.")

    payload = {
        "model": model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_text}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }

    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.post(
                ANTHROPIC_MESSAGES_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.Timeout:
            if attempt + 1 < MAX_ATTEMPTS:
                logger.warning("Nouvelle tentative après un délai dépassé du LLM.")
                continue
            raise LLMTimeoutError("Le fournisseur LLM n'a pas répondu à temps.") from None
        except requests.RequestException:
            raise LLMServiceError("Le fournisseur LLM est indisponible.") from None

        try:
            return _parse_response(response, attempt)
        except _RetryableServiceError:
            continue

    raise LLMTimeoutError("Le fournisseur LLM n'a pas répondu à temps.")


def _parse_response(response: Any, attempt: int) -> str:
    """Traduit le statut et le contenu HTTP en résultat ou exception métier."""
    status_code = getattr(response, "status_code", None)
    if status_code == 429:
        raise LLMQuotaError("Le quota du fournisseur LLM est dépassé.")
    if status_code in (401, 403):
        raise LLMAuthError("L'authentification du fournisseur LLM a échoué.")
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        if attempt + 1 < MAX_ATTEMPTS:
            logger.warning("Nouvelle tentative après une erreur temporaire du LLM.")
            return _retry_after_service_error()
        raise LLMServiceError("Le fournisseur LLM est indisponible.")
    if not isinstance(status_code, int) or not 200 <= status_code <= 299:
        raise LLMResponseError("La réponse du fournisseur LLM est invalide.")

    try:
        body = response.json()
    except (AttributeError, TypeError, ValueError):
        raise LLMResponseError("La réponse du fournisseur LLM est invalide.") from None
    if not isinstance(body, dict):
        raise LLMResponseError("La réponse du fournisseur LLM est invalide.")

    content = body.get("content")
    if not isinstance(content, list) or not content:
        raise LLMResponseError("La réponse du fournisseur LLM est invalide.")
    first_block = content[0]
    if not isinstance(first_block, dict) or first_block.get("type") != "text":
        raise LLMResponseError("La réponse du fournisseur LLM est invalide.")
    text = first_block.get("text")
    if not isinstance(text, str) or not text:
        raise LLMResponseError("La réponse du fournisseur LLM est invalide.")
    return text


def _retry_after_service_error() -> str:
    """Signale au flux principal qu'un nouvel appel est nécessaire."""
    raise _RetryableServiceError


class _RetryableServiceError(Exception):
    """Signal interne pour relancer une requête après une erreur 5xx."""
