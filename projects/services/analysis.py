"""Service d'analyse IA des projets."""

import logging
import json

from django.conf import settings

from projects.ai.client import call_llm
from projects.ai.exceptions import LLMError
from projects.ai.prompts import ANALYSIS_SYSTEM_PROMPT
from projects.ai.retrieval import retrieve_reference
from projects.ai.sanitizer import (
    MAX_DESCRIPTION_CHARS_LLM,
    MAX_NAME_CHARS_LLM,
    sanitize_project_text,
    neutralize_text,
)
from projects.ai.validators import parse_analysis_response
from projects.models import Project, ProjectAnalysis


logger = logging.getLogger(__name__)
GENERIC_LLM_ERROR = "Analyse indisponible"
INTERNAL_ERROR = "Erreur interne"


def analyze_project(project: Project) -> dict:
    """Analyse un projet, historise le résultat et retourne son état."""
    user_text = _build_project_text(project)
    description = sanitize_project_text(
        project.description,
        MAX_DESCRIPTION_CHARS_LLM,
    )
    references = retrieve_reference(description)
    simulated = getattr(settings, "PROJECT_LLM_PROVIDER", "") == "mock"
    try:
        raw_response = call_llm(ANALYSIS_SYSTEM_PROMPT, user_text)
        result = parse_analysis_response(raw_response)
        result["references_used"] = [reference["nom"] for reference in references]
    except LLMError as error:
        logger.warning("Analyse LLM indisponible: type=%s", type(error).__name__)
        _save_analysis(project, None, simulated, GENERIC_LLM_ERROR)
        return _response_payload(None, simulated, GENERIC_LLM_ERROR, None)
    except Exception:
        logger.error("Erreur interne pendant l'analyse du projet.")
        _save_analysis(project, None, simulated, INTERNAL_ERROR)
        return _response_payload(None, simulated, INTERNAL_ERROR, None)

    analysis = _save_analysis(project, result, simulated, None)
    project.status = Project.Status.ANALYZED
    project.save(update_fields=("status", "updated_at"))
    return _response_payload(result, simulated, None, analysis.created_at)


def _build_project_text(project: Project) -> str:
    """Construit le texte utilisateur avec les champs projet assainis."""
    name = sanitize_project_text(project.name, MAX_NAME_CHARS_LLM)
    description = sanitize_project_text(
        project.description,
        MAX_DESCRIPTION_CHARS_LLM,
    )
    project_text = (
        "<projet>\n"
        f"nom : {name}\n"
        f"description : {description}\n"
        f"date limite : {project.deadline.isoformat()}\n"
        f"montant estimé : {project.estimated_amount}\n"
        "</projet>"
    )
    references = retrieve_reference(description)
    if not references:
        return project_text
    reference_json = neutralize_text(
        json.dumps(references, ensure_ascii=False)
    )
    return f"{project_text}\n<reference>\n{reference_json}\n</reference>"


def _save_analysis(
    project: Project,
    result: dict | None,
    simulated: bool,
    error: str | None,
) -> ProjectAnalysis:
    """Enregistre une analyse sans stocker le texte transmis au LLM."""
    return ProjectAnalysis.objects.create(
        project=project,
        result=result,
        simulated=simulated,
        error=error,
    )


def _response_payload(
    result: dict | None,
    simulated: bool,
    error: str | None,
    analyzed_at,
) -> dict:
    """Construit la réponse publique stable du service."""
    return {
        "result": result,
        "simulated": simulated,
        "error": error,
        "analyzed_at": analyzed_at,
    }
