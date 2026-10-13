"""Simulateur local d'analyse de projets."""

import json
import re
from decimal import Decimal

from .validators import parse_analysis_response


def simulate_analysis(project_text: str) -> str:
    """Produit une analyse cohérente à partir de règles locales simples."""
    text = project_text.casefold()
    description_match = re.search(
        r"description\s*:\s*(.*?)(?:\n|$)",
        project_text,
        flags=re.IGNORECASE,
    )
    description = description_match.group(1) if description_match else project_text
    description_length = len(description.strip())
    keywords = {
        "mobile": "Développement mobile",
        "site": "Développement web",
        "paiement": "Paiement et sécurité",
    }
    specialities = [
        {"nom": speciality, "nb": 1}
        for keyword, speciality in keywords.items()
        if keyword in text
    ]
    if not specialities:
        specialities = [{"nom": "Développement généraliste", "nb": 1}]

    complexity = "ELEVEE" if len(specialities) >= 2 or description_length > 500 else "MOYENNE"
    amount_match = re.search(r"montant estimé\s*:\s*([\d.,]+)", project_text, re.IGNORECASE)
    amount = Decimal("0")
    if amount_match:
        amount = Decimal(amount_match.group(1).replace(",", "."))
    budget_min = amount * Decimal("0.8")
    budget_max = amount * Decimal("1.2")
    if amount < Decimal("1000") and complexity == "ELEVEE":
        coherence = "SOUS_ESTIME"
    else:
        coherence = "COHERENT"

    result = {
        "budget_min": float(budget_min),
        "budget_max": float(budget_max),
        "devise": "EUR",
        "nb_freelancers": len(specialities),
        "specialites": specialities,
        "duree_semaines": 12 if complexity == "ELEVEE" else 8,
        "complexite": complexity,
        "risques": (
            ["Description trop vague : les estimations sont peu fiables."]
            if description_length < 30
            else ["Les dépendances techniques devront être précisées."]
        ),
        "jalons": ["Cadrage", "Développement", "Recette"],
        "coherence_budget": coherence,
        "recommandation": "Préciser les critères de réussite avant le lancement.",
        "confiance": 0.4 if description_length < 30 else 0.8,
    }
    return json.dumps(parse_analysis_response(json.dumps(result)), ensure_ascii=False)
