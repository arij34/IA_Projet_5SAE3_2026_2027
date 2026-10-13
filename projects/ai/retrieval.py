"""Récupération locale de références par TF-IDF et similarité cosinus."""

import json
import math
import re
import unicodedata
from pathlib import Path

from projects.ai.sanitizer import MAX_DESCRIPTION_CHARS_LLM, sanitize_project_text
from projects.models import ProjectAnalysis


REFERENCE_DATA_PATH = Path(__file__).with_name("reference_data.json")
FAQ_DATA_PATH = Path(__file__).with_name("faq_data.json")
MIN_COSINE_SIMILARITY = 0.12
MIN_CORPUS_COSINE_SIMILARITY = 0.12
DEFAULT_REFERENCE_COUNT = 3
DEFAULT_CORPUS_COUNT = 3
MAX_ANALYSIS_BLOCK_CHARS = MAX_DESCRIPTION_CHARS_LLM
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


def retrieve_corpus(
    corpus: list[dict],
    question: str,
    k: int = DEFAULT_CORPUS_COUNT,
) -> list[dict]:
    """Retourne les blocs les plus proches d'une question selon leur contenu."""
    if not isinstance(question, str) or not isinstance(k, int) or k <= 0:
        return []
    valid_corpus = [block for block in corpus if isinstance(block, dict)]
    if not valid_corpus:
        return []
    documents = [_corpus_block_text(block) for block in valid_corpus]
    query_tokens = _tokens(question)
    if not query_tokens:
        return []
    document_tokens = [_tokens(document) for document in documents]
    vocabulary = set(query_tokens)
    for tokens in document_tokens:
        vocabulary.update(tokens)
    idf = _idf(document_tokens, vocabulary)
    query_vector = _tfidf(query_tokens, idf)
    scored = []
    for block, tokens in zip(valid_corpus, document_tokens):
        score = _cosine_similarity(query_vector, _tfidf(tokens, idf))
        if score >= MIN_CORPUS_COSINE_SIMILARITY:
            scored.append((score, block))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
    return [block for _, block in scored[:k]]


def load_faq_corpus() -> list[dict]:
    """Charge le corpus FAQ statique local."""
    with FAQ_DATA_PATH.open(encoding="utf-8") as faq_file:
        data = json.load(faq_file)
    return data if isinstance(data, list) else []


def build_user_analysis_corpus(user) -> list[dict]:
    """Construit les blocs d'analyse validée appartenant à l'utilisateur."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    analyses = (
        ProjectAnalysis.objects.filter(
            project__owner=user,
            result__isnull=False,
            error__isnull=True,
        )
        .select_related("project")
        .order_by("-created_at")
    )
    blocks = []
    for analysis in analyses:
        project = analysis.project
        raw_block = {
            "id": f"analysis-{analysis.pk}",
            "question": f"Analyse du projet {project.name}",
            "reponse": json.dumps(analysis.result, ensure_ascii=False),
        }
        sanitized_block = {
            **raw_block,
            "question": sanitize_project_text(
                raw_block["question"],
                MAX_ANALYSIS_BLOCK_CHARS,
            ),
            "reponse": sanitize_project_text(
                raw_block["reponse"],
                MAX_ANALYSIS_BLOCK_CHARS,
            ),
        }
        blocks.append(sanitized_block)
    return blocks


def retrieve_faq(question: str, k: int = DEFAULT_CORPUS_COUNT) -> list[dict]:
    """Recherche une question dans le corpus FAQ local."""
    return retrieve_corpus(load_faq_corpus(), question, k)


def retrieve_user_analysis(
    user,
    question: str,
    k: int = DEFAULT_CORPUS_COUNT,
) -> list[dict]:
    """Recherche dans les analyses validées des projets de l'utilisateur."""
    return retrieve_corpus(build_user_analysis_corpus(user), question, k)


def _corpus_block_text(block: dict) -> str:
    """Transforme un bloc de corpus en texte indexable."""
    return " ".join(
        str(value)
        for key, value in block.items()
        if key != "id" and isinstance(value, (str, int, float))
    )


def _load_references() -> list[dict]:
    """Charge les références locales depuis le fichier JSON."""
    with REFERENCE_DATA_PATH.open(encoding="utf-8") as reference_file:
        data = json.load(reference_file)
    return data if isinstance(data, list) else []


def _reference_text(reference: dict) -> str:
    """Construit le texte indexé d'une référence."""
    phases = " ".join(reference.get("phases_habituelles", []))
    team = " ".join(reference.get("equipe_type", []))
    return " ".join(
        [
            reference.get("nom", ""),
            " ".join(reference.get("mots_cles", [])),
            reference.get("description", ""),
            phases,
            team,
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
