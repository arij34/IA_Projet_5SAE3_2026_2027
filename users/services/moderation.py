"""Service de modération automatique des profils utilisateur."""

import re
from typing import Any
from unicodedata import normalize

from django.db import transaction

from users.ai.anonymizer import anonymize_fields
from users.ai.exceptions import LLMError
from users.ai.llm_client import call_llm
from users.ai.prompts import MODERATION_SYSTEM_PROMPT
from users.ai.validators import parse_moderation_response
from users.models import ModerationLog, User

CONFIDENCE_THRESHOLD = 0.7
MAX_TITLE_CHARS = 200
MAX_BIO_CHARS = 2000
MAX_SKILLS = 30
MAX_SKILL_CHARS = 50
MAX_REASON_CHARS = 500
_PLACEHOLDER_RE = re.compile(r"\[[^\[\]]*\]")


def _neutralize_profile_text(value: Any) -> Any:
    """Neutralise les chevrons présents dans un texte."""
    if isinstance(value, str):
        return value.replace("<", "‹").replace(">", "›")
    if isinstance(value, dict):
        return {
            key: _neutralize_profile_text(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_neutralize_profile_text(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_neutralize_profile_text(item) for item in value)
    return value


def _normalize_profile_text(value: Any) -> Any:
    """Normalise récursivement les textes utilisateur en NFKC."""
    if isinstance(value, str):
        return normalize("NFKC", value)
    if isinstance(value, dict):
        return {
            key: _normalize_profile_text(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_profile_text(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_profile_text(item) for item in value)
    return value


def _truncate_text(text: str, max_chars: int) -> str:
    """Tronque un texte sans couper un placeholder d'anonymisation."""
    result: list[str] = []
    consumed = 0
    position = 0

    for match in _PLACEHOLDER_RE.finditer(text):
        plain_text = text[position : match.start()]
        remaining = max_chars - consumed
        if remaining <= 0:
            break
        if len(plain_text) > remaining:
            result.append(plain_text[:remaining])
            return "".join(result)
        result.append(plain_text)
        consumed += len(plain_text)

        placeholder = match.group(0)
        remaining = max_chars - consumed
        if len(placeholder) > remaining:
            break
        result.append(placeholder)
        consumed += len(placeholder)
        position = match.end()
    else:
        remaining = max_chars - consumed
        result.append(text[position : position + max(remaining, 0)])

    return "".join(result)


def _truncate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Limite la taille des champs après anonymisation et neutralisation."""
    return {
        "title": _truncate_text(profile["title"], MAX_TITLE_CHARS),
        "bio": _truncate_text(profile["bio"], MAX_BIO_CHARS),
        "skills": [
            _truncate_text(str(skill), MAX_SKILL_CHARS)
            for skill in profile["skills"][:MAX_SKILLS]
        ],
    }


def _is_empty_profile(profile: dict[str, Any]) -> bool:
    """Indique si le titre, la bio et les compétences sont tous vides."""
    return not any(
        (
            str(profile["title"]).strip(),
            str(profile["bio"]).strip(),
            any(str(skill).strip() for skill in profile["skills"]),
        )
    )


def _profile_message(profile: dict[str, Any]) -> str:
    """Construit le contenu délimité envoyé au LLM."""
    return (
        "<profil>\n"
        f"Titre : {profile['title']}\n"
        f"Biographie : {profile['bio']}\n"
        f"Compétences : {', '.join(str(skill) for skill in profile['skills'])}\n"
        "</profil>"
    )


def _save_moderation(
    user: User,
    decision: str,
    reason: str,
    confidence: float | None,
    error: str = "",
) -> ModerationLog:
    """Crée une entrée d'historique sans modifier le compte utilisateur."""
    with transaction.atomic():
        return ModerationLog.objects.create(
            user=user,
            decision=decision,
            reason=reason[:MAX_REASON_CHARS],
            confidence=confidence,
            error=error,
        )


def moderate_user_profile(user: User) -> ModerationLog | None:
    """Modère le profil d'un utilisateur et retourne le journal créé."""
    if user.role == User.Role.ADMIN:
        return None

    profile = {
        "title": user.title or "",
        "bio": user.bio or "",
        "skills": user.skills or [],
    }
    if _is_empty_profile(profile):
        return _save_moderation(
            user,
            User.ModerationStatus.OK,
            "Profil vide, rien à modérer",
            None,
        )

    known_names = (user.username, user.first_name, user.last_name)
    safe_profile = _normalize_profile_text(profile)
    safe_profile = anonymize_fields(safe_profile, known_names=known_names)
    safe_profile = _truncate_profile(safe_profile)
    safe_profile = _neutralize_profile_text(safe_profile)

    try:
        response = call_llm(
            MODERATION_SYSTEM_PROMPT,
            _profile_message(safe_profile),
        )
        parsed = parse_moderation_response(response)
    except LLMError as exc:
        return _save_moderation(
            user,
            User.ModerationStatus.SUSPECT,
            "Vérification automatique indisponible : revue manuelle",
            None,
            type(exc).__name__,
        )

    decision = parsed["statut"]
    confidence = parsed["confiance"]
    if (
        decision == User.ModerationStatus.OK
        and confidence < CONFIDENCE_THRESHOLD
    ):
        decision = User.ModerationStatus.SUSPECT

    return _save_moderation(
        user,
        decision,
        parsed["raison"],
        confidence,
    )
