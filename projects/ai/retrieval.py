"""Récupération locale de références par TF-IDF et similarité cosinus."""

import json
import math
import re
import unicodedata
from pathlib import Path


REFERENCE_DATA_PATH = Path(__file__).with_name("reference_data.json")
MIN_COSINE_SIMILARITY = 0.12
DEFAULT_REFERENCE_COUNT = 3
_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def retrieve_reference(description: str, k: int = DEFAULT_REFERENCE_COUNT) -> list[dict]:
    """Retourne les références les plus proches de la description."""
    if not isinstance(description, str) or k <= 0:
        return []
    references = _load_references()
    documents = [_reference_text(reference) for reference in references]
    query_tokens = _tokens(description)
    if not query_tokens:
        return []

    document_tokens = [_tokens(document) for document in documents]
    vocabulary = set(query_tokens)
    for tokens in document_tokens:
        vocabulary.update(tokens)
    idf = _idf(document_tokens, vocabulary)
    query_vector = _tfidf(query_tokens, idf)
    scored = []
    for reference, tokens in zip(references, document_tokens):
        score = _cosine_similarity(query_vector, _tfidf(tokens, idf))
        if score >= MIN_COSINE_SIMILARITY:
            scored.append((score, reference))
    scored.sort(key=lambda item: (-item[0], item[1]["nom"]))
    return [reference for _, reference in scored[:k]]


def _load_references() -> list[dict]:
    """Charge les références locales depuis le fichier JSON."""
    with REFERENCE_DATA_PATH.open(encoding="utf-8") as reference_file:
        data = json.load(reference_file)
    return data if isinstance(data, list) else []


def _reference_text(reference: dict) -> str:
    """Construit le texte indexé d'une référence."""
    return " ".join(
        [
            reference.get("nom", ""),
            " ".join(reference.get("mots_cles", [])),
            reference.get("description", ""),
        ]
    )


def _tokens(text: str) -> list[str]:
    """Tokenise sans dépendance externe et sans distinguer les accents."""
    folded = unicodedata.normalize("NFKD", text).casefold()
    plain = "".join(character for character in folded if not unicodedata.combining(character))
    return _TOKEN_PATTERN.findall(plain)


def _idf(documents: list[list[str]], vocabulary: set[str]) -> dict[str, float]:
    """Calcule l'IDF lissé pour le corpus local."""
    document_count = len(documents)
    return {
        term: math.log((1 + document_count) / (1 + sum(term in document for document in documents))) + 1
        for term in vocabulary
    }


def _tfidf(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Construit un vecteur TF-IDF normalisé par les fréquences."""
    if not tokens:
        return {}
    counts = {token: tokens.count(token) for token in set(tokens)}
    total = len(tokens)
    return {
        token: (count / total) * idf[token]
        for token, count in counts.items()
    }


def _cosine_similarity(first: dict[str, float], second: dict[str, float]) -> float:
    """Calcule une similarité cosinus bornée entre 0 et 1."""
    if not first or not second:
        return 0.0
    dot_product = sum(first.get(term, 0.0) * value for term, value in second.items())
    first_norm = math.sqrt(sum(value * value for value in first.values()))
    second_norm = math.sqrt(sum(value * value for value in second.values()))
    if not first_norm or not second_norm:
        return 0.0
    return max(0.0, min(1.0, dot_product / (first_norm * second_norm)))
