"""Récupération lexicale locale (TF-IDF) pour le RAG de génération de quiz.

Pas de base vectorielle ni d'API d'embeddings : la base de connaissances est petite
(quelques dizaines d'extraits attribués), un TF-IDF en mémoire suffit et reste
déterministe, gratuit et testable hors-ligne. Limite connue : la correspondance est
lexicale, donc un sujet formulé en français ne retrouve un extrait anglais que grâce
aux mots-clés bilingues du corpus et au filtre de catégorie.
"""

import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from django.conf import settings

KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent.parent / "rag_data" / "knowledge_base.json"
DEFAULT_TOP_K = 3
DEFAULT_MAX_CHARS = 3000
MAX_CHUNK_CHARS = 700
MIN_SCORE = 0.05
DIFFICULTY_BONUS = 0.1
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return [t for t in _TOKEN.findall(stripped) if len(t) > 1]


def split_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split on sentence boundaries into pieces of at most ~max_chars characters."""
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def load_chunks(path: Path = KNOWLEDGE_BASE_PATH) -> list[dict]:
    """Load the knowledge base and chunk every document (invalid or empty ones are skipped)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    chunks = []
    for doc in data.get("chunks", []) if isinstance(data, dict) else []:
        if not all(doc.get(key) for key in ("id", "categories", "source_url", "source_title", "text")):
            continue
        parts = split_text(doc["text"])
        for index, part in enumerate(parts):
            chunks.append(
                {
                    "id": doc["id"] if len(parts) == 1 else f"{doc['id']}#{index + 1}",
                    "categories": list(doc["categories"]),
                    "difficulty": list(doc.get("difficulty", [])),
                    "keywords": doc.get("keywords", ""),
                    "source_title": doc["source_title"],
                    "source_url": doc["source_url"],
                    "text": part,
                }
            )
    return chunks


@lru_cache(maxsize=1)
def _default_chunks() -> tuple:
    return tuple(load_chunks())


def _vectors(token_lists: list[list[str]]):
    document_count = len(token_lists)
    frequency = {}
    for tokens in token_lists:
        for token in set(tokens):
            frequency[token] = frequency.get(token, 0) + 1
    idf = {t: math.log((1 + document_count) / (1 + n)) + 1 for t, n in frequency.items()}
    return idf


def _weights(tokens: list[str], idf: dict) -> dict:
    counts = {}
    for token in tokens:
        if token in idf:
            counts[token] = counts.get(token, 0) + 1
    return {t: (1 + math.log(c)) * idf[t] for t, c in counts.items()}


def _cosine(a: dict, b: dict) -> float:
    dot = sum(w * b.get(t, 0.0) for t, w in a.items())
    norm = math.sqrt(sum(w * w for w in a.values())) * math.sqrt(sum(w * w for w in b.values()))
    return dot / norm if norm else 0.0


def retrieve_context(
    category_slug: str,
    difficulty: str,
    objective: str = "",
    *,
    k: int | None = None,
    max_chars: int | None = None,
    chunks=None,
) -> list[dict]:
    """Return the most relevant attributed chunks for a technology, level and objective.

    The category is a hard filter (no cross-technology context); relevance is the TF-IDF
    cosine between the query and a chunk, plus a small bonus when the chunk targets the
    requested difficulty. Chunks scoring below MIN_SCORE are dropped, so the result may be
    empty; callers must then fall back to the non-RAG prompt.
    """
    k = k if k is not None else getattr(settings, "CHALLENGE_RAG_TOP_K", DEFAULT_TOP_K)
    max_chars = (
        max_chars if max_chars is not None else getattr(settings, "CHALLENGE_RAG_MAX_CHARS", DEFAULT_MAX_CHARS)
    )
    pool = list(_default_chunks() if chunks is None else chunks)
    candidates = [c for c in pool if category_slug in c["categories"]]
    if not candidates or k <= 0 or max_chars <= 0:
        return []
    chunk_tokens = [_tokens(f"{c['keywords']} {c['source_title']} {c['text']}") for c in candidates]
    idf = _vectors(chunk_tokens)
    query = _weights(_tokens(f"{category_slug} {objective}"), idf)
    scored = []
    for chunk, tokens in zip(candidates, chunk_tokens):
        lexical = _cosine(query, _weights(tokens, idf))
        if objective.strip() and lexical < MIN_SCORE:
            continue  # with an explicit objective, the difficulty bonus alone must not admit a chunk
        score = lexical
        if difficulty in chunk["difficulty"]:
            score += DIFFICULTY_BONUS
        if score >= MIN_SCORE:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))

    selected, used = [], 0
    for score, chunk in scored[:k]:
        if used + len(chunk["text"]) > max_chars:
            continue
        used += len(chunk["text"])
        selected.append({**chunk, "score": round(score, 4)})
    return selected


def format_sources(selected: list[dict]) -> str:
    """Render the selected chunks as numbered, attributed source blocks."""
    return "\n\n".join(
        f"[S{i}] {c['source_title']} — {c['source_url']}\n{c['text']}"
        for i, c in enumerate(selected, start=1)
    )
