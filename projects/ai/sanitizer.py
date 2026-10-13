"""Nettoyage des textes de projets avant leur transmission à un LLM."""

import re
import unicodedata


MAX_NAME_CHARS_LLM = 150
MAX_DESCRIPTION_CHARS_LLM = 3000

_EMAIL_PATTERN = re.compile(
    r"(?<![\w.!#$%&'*+/=?^`{|}~-])"
    r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+"
    r"(?![\w.!#$%&'*+/=?^`{|}~-])",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"
)
_LINK_PATTERN = re.compile(
    r"(?<!\w)(?:https?://|www\.)[^\s<>()]+",
    re.IGNORECASE,
)
_PLACEHOLDER_PATTERN = re.compile(r"\[(?:EMAIL|TEL|LIEN)\]")


def normalize_text(text: str) -> str:
    """Normalise le texte avec la forme Unicode NFKC uniquement."""
    return unicodedata.normalize("NFKC", text)


def anonymize_text(text: str) -> str:
    """Remplace les adresses e-mail, téléphones et liens par des placeholders."""
    text = _EMAIL_PATTERN.sub("[EMAIL]", text)
    text = _PHONE_PATTERN.sub("[TEL]", text)
    return _LINK_PATTERN.sub("[LIEN]", text)


def truncate_text(text: str, max_chars: int) -> str:
    """Tronque le texte sans couper un placeholder d'anonymisation."""
    if max_chars < 0:
        raise ValueError("max_chars doit être positif ou nul.")
    if len(text) <= max_chars:
        return text

    cut = max_chars
    for match in _PLACEHOLDER_PATTERN.finditer(text):
        if match.start() < cut < match.end():
            cut = match.start()
            break
    return text[:cut]


def neutralize_text(text: str) -> str:
    """Remplace uniquement les chevrons ASCII par des chevrons typographiques."""
    return text.replace("<", "‹").replace(">", "›")


def sanitize_project_text(text: str, max_chars: int) -> str:
    """Applique dans l'ordre fixe normalisation, anonymisation, troncature et neutralisation."""
    normalized = normalize_text(text)
    anonymized = anonymize_text(normalized)
    truncated = truncate_text(anonymized, max_chars)
    return neutralize_text(truncated)
