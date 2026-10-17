"""Normalisation de texte partagée par les services de matching."""

import re
import unicodedata

_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9+#]+")

# Synonymes usuels permettant de rapprocher des libellés équivalents sans LLM.
SYNONYMS = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "ml": "machine learning",
    "ia": "intelligence artificielle",
    "ai": "intelligence artificielle",
    "bdd": "base de donnees",
    "db": "base de donnees",
    "front": "frontend",
    "back": "backend",
    "secu": "securite",
    "cyber": "securite",
    "devops": "devops",
}

# Mots sans valeur discriminante dans un libellé de compétence.
STOP_WORDS = frozenset(
    {
        "et", "de", "des", "du", "la", "le", "les", "un", "une", "en", "pour",
        "developpement", "developpeur", "developpeuse", "ingenieur", "expert",
        "specialiste", "consultant", "architecture", "architecte",
    }
)

# Langages dont le nom tient en une lettre : ils doivent survivre au filtrage
# des jetons d'une seule lettre produits par la coupure des mots composés
# (« e-commerce » donnerait sinon un jeton parasite « e »).
SINGLE_LETTER_SKILLS = frozenset({"c", "r"})


def strip_accents(value: str) -> str:
    """Retire les accents d'une chaîne sans modifier les autres caractères."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(value: object) -> str:
    """Normalise une valeur en minuscules sans accent ni ponctuation."""
    text = strip_accents(str(value or "")).lower()
    return " ".join(_SEPARATOR_PATTERN.sub(" ", text).split())


def _is_meaningful(token: str) -> bool:
    """Écarte les mots vides et les jetons d'une lettre sans signification."""
    if not token or token in STOP_WORDS:
        return False
    if len(token) == 1:
        return token in SINGLE_LETTER_SKILLS
    return True


def tokenize(value: object) -> set[str]:
    """Découpe une valeur en jetons normalisés, synonymes appliqués."""
    tokens: set[str] = set()
    for token in normalize(value).split():
        expanded = SYNONYMS.get(token, token)
        for part in expanded.split():
            if _is_meaningful(part):
                tokens.add(part)
    return tokens


def tokenize_all(values) -> set[str]:
    """Agrège les jetons normalisés d'une collection de valeurs."""
    tokens: set[str] = set()
    for value in values or ():
        tokens |= tokenize(value)
    return tokens


def overlap_ratio(required: set[str], available: set[str]) -> float:
    """Retourne la part des jetons requis couverts par les jetons disponibles."""
    if not required:
        return 0.0
    return len(required & available) / len(required)
