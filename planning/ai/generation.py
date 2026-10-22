import json
import re
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

from users.ai.llm_client import call_llm

from .prompts import SYSTEM_PROMPT


TASK_DESCRIPTION_MAX_LENGTH = 2000
TASK_NAME_MIN_LENGTH = 3
TASK_NAME_MAX_LENGTH = 100


def generate_tasks(project_name: str) -> tuple[list[dict], bool]:
    """Generate validated tasks; return deterministic fallback on any provider failure."""
    if getattr(settings, "LLM_PROVIDER", "mock") == "mock":
        return fallback_tasks(project_name), True
    try:
        raw = call_llm(SYSTEM_PROMPT, project_name, max_tokens=1600)
        return validate_generated_tasks(raw, timezone.localdate()), False
    except Exception:
        return fallback_tasks(project_name), True


def validate_generated_tasks(raw: str, today: date | None = None) -> list[dict]:
    """Parse provider output and enforce the complete generated-task contract."""
    if not isinstance(raw, str):
        raise ValueError("La réponse IA doit être du texte JSON.")
    text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    payload = json.loads(text)
    tasks = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(tasks, list) or len(tasks) != 3:
        raise ValueError("La réponse doit contenir exactement trois tâches.")

    current_date = today or date.today()
    validated = []
    required = {"name", "description", "start_date", "end_date"}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict) or not required.issubset(task):
            raise ValueError("Une tâche ne contient pas tous les champs obligatoires.")
        name = task["name"].strip() if isinstance(task["name"], str) else ""
        description = task["description"].strip() if isinstance(task["description"], str) else ""
        if not TASK_NAME_MIN_LENGTH <= len(name) <= TASK_NAME_MAX_LENGTH:
            raise ValueError("Le nom d'une tâche doit contenir entre 3 et 100 caractères.")
        if not description or len(description) > TASK_DESCRIPTION_MAX_LENGTH:
            raise ValueError("La description d'une tâche est invalide.")
        start = _parse_iso_date(task["start_date"])
        end = _parse_iso_date(task["end_date"])
        if end < start:
            raise ValueError("La date de fin précède la date de début.")
        duration = (end - start).days + 1
        if not 3 <= duration <= 7:
            raise ValueError("Chaque tâche générée doit durer de 3 à 7 jours.")
        expected_start = current_date if index == 0 else validated[index - 1]["_end"] + timedelta(days=1)
        if start != expected_start:
            raise ValueError("Les tâches générées doivent être séquentielles et commencer aujourd'hui.")
        validated.append(
            {
                "name": name,
                "description": description,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "_end": end,
            }
        )
    for task in validated:
        task.pop("_end")
    return validated


def _parse_iso_date(value) -> date:
    if not isinstance(value, str):
        raise ValueError("La date doit être au format ISO YYYY-MM-DD.")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("La date doit être au format ISO YYYY-MM-DD.")
    return parsed


def fallback_tasks(project_name: str, today: date | None = None) -> list[dict]:
    """Create three sequential, realistic tasks when the configured provider is unavailable."""
    start = today or timezone.localdate()
    french = _is_french_name(project_name)
    if french:
        items = (
            ("Cadrage du projet", "Préciser les objectifs, le périmètre et les critères de réussite."),
            ("Conception de la solution", "Définir l'architecture, les étapes de réalisation et les livrables."),
            ("Réalisation et validation", "Construire une première version, la vérifier et préparer sa livraison."),
        )
    else:
        items = (
            ("Project discovery", "Clarify the goals, scope, and success criteria."),
            ("Solution design", "Define the approach, delivery steps, and expected outputs."),
            ("Build and review", "Create an initial version, validate it, and prepare delivery."),
        )
    result = []
    for name, description in items:
        end = start + timedelta(days=3)
        result.append(
            {
                "name": name,
                "description": f"{project_name}: {description}",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
        )
        start = end + timedelta(days=1)
    return result


def _is_french_name(project_name: str) -> bool:
    words = set(re.findall(r"[a-zà-ÿ]+", project_name.casefold()))
    french_markers = {"projet", "création", "creer", "créer", "application", "site", "plateforme", "développement", "developpement", "gestion"}
    english_markers = {"project", "website", "redesign", "build", "platform"}
    if words & french_markers or any(char in project_name for char in "àâçéèêëîïôùûüÿœ"):
        return True
    if words & english_markers:
        return False
    return True
