"""Anonymisation des textes AVANT tout envoi à un LLM.

Exigence du cahier des charges : jamais de données personnelles brutes
envoyées au LLM. Cette version est basée sur des expressions régulières
(approche "au mieux") : elle retire emails, liens, numéros de téléphone
et les noms connus de l'utilisateur.
"""
import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<![\w])\+?\d[\d\s().-]{6,}\d(?![\w])")
YEAR_RANGE_RE = re.compile(r"(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}")

MIN_PHONE_DIGITS = 8


def _replace_phone(match: re.Match) -> str:
    """Remplace un numéro de téléphone, mais garde les périodes comme 2019-2023."""
    value = match.group(0)
    if YEAR_RANGE_RE.fullmatch(value.strip()):
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) < MIN_PHONE_DIGITS:
        return value
    return "[TELEPHONE]"


def anonymize_text(text, known_names=()):
    """Retourne le texte sans email, lien, téléphone ni nom connu."""
    if not text:
        return ""
    result = EMAIL_RE.sub("[EMAIL]", str(text))
    result = URL_RE.sub("[LIEN]", result)
    result = PHONE_RE.sub(_replace_phone, result)
    for name in known_names:
        cleaned = (name or "").strip()
        if len(cleaned) >= 2:
            result = re.sub(re.escape(cleaned), "[NOM]", result, flags=re.IGNORECASE)
    return result


def anonymize_fields(data: dict, known_names=()) -> dict:
    """Anonymise toutes les valeurs texte (et listes de textes) d'un dictionnaire."""
    safe = {}
    for key, value in data.items():
        if isinstance(value, str):
            safe[key] = anonymize_text(value, known_names)
        elif isinstance(value, (list, tuple)):
            safe[key] = [
                anonymize_text(item, known_names) if isinstance(item, str) else item
                for item in value
            ]
        else:
            safe[key] = value
    return safe
