"""Client unique pour appeler le LLM depuis Django.

Fournisseurs (variable LLM_PROVIDER dans .env) :
- "mock"      : réponses simulées, sans clé API (développement et tests)
- "anthropic" : API Claude
- "gemini"    : API Gemini

Le LLM n'est jamais appelé depuis React : la clé reste côté serveur.
"""
import logging
import re
from collections import Counter
from unicodedata import combining, normalize

import requests
from django.conf import settings

from .exceptions import (
    LLMConfigError,
    LLMError,
    LLMQuotaError,
    LLMResponseError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_ATTEMPTS = 2  # 1 appel + 1 nouvel essai sur erreur temporaire
_MOCK_CRITERIA_IDS = (
    "paiement_hors_plateforme",
    "promesses_irrealistes",
    "spam_incoherence",
    "contenu_interdit",
    "profil_trop_pauvre",
)


def call_llm(system_prompt: str, user_content: str, max_tokens: int = 500) -> str:
    """Envoie le prompt au LLM et retourne le texte brut de la réponse."""
    provider = getattr(settings, "LLM_PROVIDER", "mock")
    if provider == "mock":
        return _call_mock(system_prompt, user_content)
    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_content, max_tokens)
    if provider == "gemini":
        return _call_gemini(system_prompt, user_content, 1024)
    raise LLMConfigError(f"Fournisseur LLM inconnu : {provider!r}")


def _call_mock(system_prompt: str, user_content: str) -> str:
    """Produit une réponse simulée réaliste pour chaque type de fonctionnalité."""
    if "statut" in system_prompt.lower():
        return _mock_moderation_response(user_content)
    return (
        '{"score": 60, "points_faibles": ["Bio trop courte (réponse simulée)"], '
        '"suggestions": ["Ajoutez vos réalisations principales (réponse simulée)"]}'
    )


def _mock_moderation_response(user_content: str) -> str:
    """Analyse les signaux de modération dans le profil transmis au mock."""
    profile_match = re.search(
        r"<profil>(.*?)</profil>",
        user_content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    profile_text = profile_match.group(1) if profile_match else user_content
    normalized = _fold_text(profile_text)
    content = re.sub(
        r"\b(?:titre|biographie|compétences)\s*:\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    repeated_word = any(
        count > 8 for count in Counter(re.findall(r"\b\w+\b", content)).values()
    )
    forbidden = any(
        phrase in normalized
        for phrase in ("escroquerie", "arnaque garantie", "contenu pour adultes")
    )
    payment = any(
        phrase in normalized
        for phrase in (
            "payez-moi d'abord",
            "paiement hors plateforme",
            "virement avant",
            "whatsapp",
            "telegram",
        )
    )
    unrealistic = any(
        phrase in normalized
        for phrase in (
            "100 % garanti",
            "garantie 100",
            "gagnez de l'argent facilement",
        )
    )
    spam = repeated_word
    poor = len(content.strip()) < 40

    if forbidden:
        decision, confidence = "REJETE", 0.95
        reason = "Contenu interdit détecté : l'IA est très sûre de ce verdict."
    elif payment or unrealistic or spam:
        decision, confidence = "SUSPECT", 0.85
        reason = "Un signal problématique a été détecté : l'IA est assez sûre de ce verdict."
    elif poor:
        decision, confidence = "OK", 0.62
        reason = "Profil très court : peu d'éléments pour juger, l'IA est peu sûre."
    else:
        decision, confidence = "OK", 0.88
        reason = "Aucun signe problématique et profil détaillé : l'IA est très sûre."

    criteria = [
        (
            "paiement_hors_plateforme",
            payment,
            "Aucune demande de paiement hors plateforme détectée."
            if not payment
            else "Un signal de paiement hors plateforme est détecté.",
        ),
        (
            "promesses_irrealistes",
            unrealistic,
            "Aucune promesse irréaliste détectée."
            if not unrealistic
            else "Une promesse irréaliste est détectée.",
        ),
        (
            "spam_incoherence",
            spam,
            "Aucune répétition excessive détectée."
            if not spam
            else "Un même mot est répété de façon excessive.",
        ),
        (
            "contenu_interdit",
            forbidden,
            "Aucun contenu interdit détecté."
            if not forbidden
            else "Un contenu interdit est détecté.",
        ),
        (
            "profil_trop_pauvre",
            poor,
            "Le profil contient assez d'éléments."
            if not poor
            else "Le profil contient trop peu d'éléments.",
        ),
    ]
    return _json_response(decision, reason, confidence, criteria)


def _fold_text(value: str) -> str:
    """Passe un texte en minuscules sans accents pour les règles du mock."""
    return "".join(
        character
        for character in normalize("NFKD", value.casefold())
        if not combining(character)
    )


def _json_response(
    decision: str,
    reason: str,
    confidence: float,
    criteria: list[tuple[str, bool, str]],
) -> str:
    """Sérialise la réponse mock de modération."""
    import json

    return json.dumps(
        {
            "statut": decision,
            "raison": reason,
            "confiance": confidence,
            "criteres": [
                {"id": criterion_id, "probleme": problem, "commentaire": comment}
                for criterion_id, problem, comment in criteria
            ],
        },
        ensure_ascii=False,
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
    response = _post_with_retries(ANTHROPIC_URL, headers, payload)
    return _extract_text(response)


def _call_gemini(
    system_prompt: str,
    user_content: str,
    max_tokens: int,
    response_mime_type: str | None = "application/json",
) -> str:
    """Envoie une requête structurée à l'API Gemini et extrait son texte."""
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise LLMConfigError("GEMINI_API_KEY est absente (vérifiez le fichier .env).")

    model = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite")
    headers = {
        "x-goog-api-key": api_key,
        "content-type": "application/json",
    }
    generation_config = {
        "maxOutputTokens": max_tokens,
        "temperature": 0.2,
    }
    if response_mime_type is not None:
        generation_config["responseMimeType"] = response_mime_type
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": generation_config,
    }
    response = _post_with_retries(
        f"{GEMINI_URL}/{model}:generateContent",
        headers,
        payload,
    )
    return _extract_gemini_text(response)


def _post_with_retries(
    url: str,
    headers: dict[str, str],
    payload: dict,
) -> requests.Response:
    """Effectue un POST avec les retries et erreurs communs aux fournisseurs."""
    timeout = settings.LLM_TIMEOUT_SECONDS
    last_error: LLMError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=timeout
            )
        except requests.Timeout:
            last_error = LLMTimeoutError("Le LLM n'a pas répondu à temps.")
            logger.warning("Timeout LLM (essai %s/%s)", attempt, MAX_ATTEMPTS)
            continue
        except requests.RequestException:
            raise LLMResponseError("Erreur réseau vers le LLM.")

        if response.status_code == 429:
            raise LLMQuotaError("Quota ou limite de requêtes dépassé.")
        if response.status_code in (400, 401, 403):
            raise LLMConfigError("Clé Gemini refusée : vérifiez GEMINI_API_KEY.")
        if response.status_code == 404:
            raise LLMConfigError("Modèle Gemini introuvable : vérifiez GEMINI_MODEL.")
        if response.status_code >= 500:
            last_error = LLMResponseError(f"Erreur serveur LLM ({response.status_code}).")
            logger.warning(
                "Erreur %s du LLM (essai %s/%s)",
                response.status_code,
                attempt,
                MAX_ATTEMPTS,
            )
            continue
        if response.status_code != 200:
            raise LLMResponseError(f"Réponse inattendue du LLM ({response.status_code}).")

        return response

    if last_error is None:
        raise LLMResponseError("Le LLM n'a pas fourni de réponse.")
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


def _extract_gemini_text(response: requests.Response) -> str:
    """Extrait et concatène les parts textuelles du premier candidat Gemini."""
    try:
        data = response.json()
        candidates = data.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts)
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise LLMResponseError("Réponse du LLM illisible.") from exc
    if not text.strip():
        raise LLMResponseError("Réponse vide du LLM.")
    return text
