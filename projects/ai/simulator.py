"""Simulateur local et déterministe d'évaluation de projets."""

import json
import re
from decimal import Decimal, ROUND_HALF_UP

from .validators import parse_analysis_response


MIN_DESCRIPTION_FOR_CONFIDENCE = 80
MIN_BUDGET = Decimal("500")
BASE_WEEKLY_FREELANCER_RATE = Decimal("300")
BUDGET_MIN_FACTOR = Decimal("0.75")
BUDGET_MAX_FACTOR = Decimal("1.35")
BUDGET_ROUNDING = Decimal("100")
PERCENTAGE_TOTAL = Decimal("100")

DOMAIN_SIGNALS = {
    "paiement": (("paiement", "transaction", "carte bancaire"), 2),
    "temps réel": (("temps réel", "temps reel", "websocket", "live"), 2),
    "intelligence artificielle": (("ia", "intelligence artificielle", "machine learning"), 2),
    "mobile": (("mobile", "android", "ios", "smartphone"), 1),
    "intégration API": (("api", "intégration", "integration", "webhook"), 1),
    "sécurité": (("sécurité", "securite", "authentification", "chiffrement"), 2),
    "e-commerce": (("e-commerce", "ecommerce", "boutique", "panier"), 1),
    "données": (("données", "donnees", "data", "base de données"), 1),
}

SPECIALITY_BY_SIGNAL = {
    "paiement": ("Paiement et sécurité", "senior"),
    "temps réel": ("Architecture temps réel", "senior"),
    "intelligence artificielle": ("Intelligence artificielle", "senior"),
    "mobile": ("Développement mobile", "confirme"),
    "intégration API": ("Intégration API", "confirme"),
    "sécurité": ("Cybersécurité", "senior"),
    "e-commerce": ("Développement e-commerce", "confirme"),
    "données": ("Data engineering", "confirme"),
}

AMOUNT_PATTERN = re.compile(
    r"montant estim[ée]?\s*:\s*([0-9]+(?:[.,][0-9]{1,2})?)",
    re.IGNORECASE,
)
DEADLINE_PATTERN = re.compile(
    r"date limite\s*:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def simulate_analysis(project_text: str) -> str:
    """Produit une évaluation complète et reproductible à partir du projet."""
    description = _extract_line(project_text, "description")

    description_length = len(description.strip())
    days_remaining = _extract_integer(project_text, "jours restants")
    amount = _extract_amount(project_text)
    signals = _detect_signals(description)
    score = _complexity_score(description_length, signals, days_remaining, amount, project_text)
    complexity = _complexity_label(score)
    duration_min, duration, duration_max = _duration_range(score, len(signals))
    specialties = _build_specialities(signals, score)
    phases = _build_phases(specialties, duration)
    budget_recommended = _recommended_budget(
        score,
        duration,
        len(specialties),
        amount,
    )
    budget_min = _round_budget(budget_recommended * BUDGET_MIN_FACTOR)
    budget_max = _round_budget(budget_recommended * BUDGET_MAX_FACTOR)
    coherence = _budget_coherence(amount, budget_recommended)
    feasibility = _deadline_feasibility(days_remaining, duration)
    success_rate = _success_rate(
        description_length,
        score,
        feasibility,
        coherence,
    )
    result = {
        "budget_min": float(budget_min),
        "budget_max": float(budget_max),
        "budget_recommande": float(budget_recommended),
        "devise": "EUR",
        "nb_freelancers": sum(item["nb"] for item in specialties),
        "specialites": specialties,
        "duree_semaines": duration,
        "duree_min_semaines": duration_min,
        "duree_max_semaines": duration_max,
        "complexite": complexity,
        "score_complexite": score,
        "facteurs_complexite": _complexity_factors(signals, description_length, days_remaining),
        "risques": _risks(signals, description_length, feasibility, coherence),
        "jalons": _milestones(phases),
        "coherence_budget": coherence,
        "justification": _budget_justification(coherence, amount, budget_recommended),
        "recommandation": "Valider le périmètre et les critères d'acceptation avant le démarrage.",
        "phases": phases,
        "faisabilite_deadline": feasibility,
        "faisabilite_deadline_justification": _deadline_justification(feasibility, days_remaining, duration),
        "taux_reussite": success_rate,
        "facteurs_positifs": _positive_factors(signals, description_length),
        "facteurs_negatifs": _negative_factors(signals, description_length, feasibility, coherence),
        "hypotheses": ["Les accès techniques et contenus nécessaires seront disponibles."],
        "questions_clarification": (
            ["Quels sont les utilisateurs cibles et les critères d'acceptation ?"]
            if description_length < MIN_DESCRIPTION_FOR_CONFIDENCE
            else []
        ),
        "recommandations": [
            "Découper le périmètre en livrables validables.",
            "Confirmer les intégrations et contraintes de sécurité.",
        ],
        "confiance": 0.45 if description_length < MIN_DESCRIPTION_FOR_CONFIDENCE else 0.8,
    }
    return json.dumps(parse_analysis_response(json.dumps(result)), ensure_ascii=False)


def _extract_line(text: str, label: str) -> str:
    """Extrait une ligne structurée du texte du projet."""
    match = re.search(rf"^{re.escape(label)}\s*:\s*(.*)$", text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_integer(text: str, label: str) -> int:
    """Extrait un entier structuré ou retourne une valeur prudente."""
    value = _extract_line(text, label)
    match = re.search(r"-?\d+", value)
    return int(match.group()) if match else 1


def _extract_amount(text: str) -> Decimal:
    """Extrait le montant structuré du projet."""
    match = AMOUNT_PATTERN.search(text)
    if not match:
        return MIN_BUDGET
    return Decimal(match.group(1).replace(",", "."))


def _detect_signals(text: str) -> dict[str, int]:
    """Compte les domaines explicitement présents dans le projet."""
    return {
        domain: weight
        for domain, (keywords, weight) in DOMAIN_SIGNALS.items()
        if any(keyword in text for keyword in keywords)
    }


def _complexity_score(
    description_length: int,
    signals: dict[str, int],
    days_remaining: int,
    amount: Decimal,
    project_text: str,
) -> int:
    """Calcule un score borné à partir de signaux mesurables."""
    score = 1
    score += min(3, description_length // 180)
    score += min(4, sum(signals.values()))
    if days_remaining < 30:
        score += 2
    elif days_remaining < 90:
        score += 1
    if amount < Decimal("5000"):
        score += 1
    if "fonctionnal" in project_text.casefold() or "exigence" in project_text.casefold():
        score += 1
    return min(10, score)


def _complexity_label(score: int) -> str:
    """Convertit le score en niveau de complexité."""
    if score <= 3:
        return "FAIBLE"
    if score <= 5:
        return "MOYENNE"
    if score <= 7:
        return "ELEVEE"
    return "TRES_ELEVEE"


def _duration_range(score: int, signal_count: int) -> tuple[int, int, int]:
    """Déduit une durée minimale, probable et maximale."""
    duration = max(3, score + signal_count * 2)
    return max(1, duration - 2), duration, min(520, duration + 4)


def _build_specialities(signals: dict[str, int], score: int) -> list[dict]:
    """Construit une équipe adaptée aux domaines détectés."""
    selected = list(signals) or ["intégration API"]
    if score >= 8 and "sécurité" not in selected:
        selected.append("sécurité")
    specialities = []
    for domain in selected[:6]:
        name, level = SPECIALITY_BY_SIGNAL[domain]
        specialities.append(
            {
                "nom": name,
                "nb": 1,
                "niveau": level,
                "charge_pourcentage": 0,
            }
        )
    total = len(specialities)
    for index, speciality in enumerate(specialities):
        speciality["charge_pourcentage"] = float(
            (PERCENTAGE_TOTAL / total).quantize(Decimal("0.01"))
        )
    specialities[-1]["charge_pourcentage"] = float(
        PERCENTAGE_TOTAL
        - sum(
            (Decimal(str(item["charge_pourcentage"]))
             for item in specialities[:-1]),
            Decimal("0"),
        )
    )
    return specialities


def _build_phases(specialities: list[dict], duration: int) -> list[dict]:
    """Construit trois phases dont les durées totalisent la durée prévue."""
    first = max(1, duration // 4)
    second = max(1, duration // 2)
    last = duration - first - second
    if last < 1:
        last = 1
        second = duration - first - last
    names = [item["nom"] for item in specialities]
    return [
        {
            "nom": "Cadrage",
            "objectif": "Préciser le périmètre et les contraintes.",
            "duree_semaines": first,
            "livrables": ["Spécifications validées"],
            "specialites": names,
            "budget_pourcentage": 20,
        },
        {
            "nom": "Réalisation",
            "objectif": "Développer les fonctionnalités prioritaires.",
            "duree_semaines": second,
            "livrables": ["Version fonctionnelle"],
            "specialites": names,
            "budget_pourcentage": 60,
        },
        {
            "nom": "Validation et déploiement",
            "objectif": "Tester, corriger et mettre en production.",
            "duree_semaines": last,
            "livrables": ["Version livrée"],
            "specialites": names,
            "budget_pourcentage": 20,
        },
    ]


def _recommended_budget(score: int, duration: int, team_size: int, amount: Decimal) -> Decimal:
    """Estime le budget nécessaire à partir de la charge."""
    base = BASE_WEEKLY_FREELANCER_RATE * duration * max(1, team_size)
    complexity_factor = Decimal("1") + Decimal(score - 1) / Decimal("20")
    return _round_budget(max(MIN_BUDGET, base * complexity_factor, amount * Decimal("0.8")))


def _round_budget(value: Decimal) -> Decimal:
    """Arrondit un budget à une centaine d'euros."""
    return (value / BUDGET_ROUNDING).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * BUDGET_ROUNDING


def _budget_coherence(amount: Decimal, recommended: Decimal) -> str:
    """Compare le budget du porteur à l'estimation calculée."""
    if amount < recommended * Decimal("0.75"):
        return "SOUS_ESTIME"
    if amount > recommended * Decimal("1.35"):
        return "SUR_ESTIME"
    return "REALISTE"


def _deadline_feasibility(days_remaining: int, duration: int) -> str:
    """Évalue la deadline par rapport à la durée estimée."""
    if days_remaining < duration * 5:
        return "IRREALISTE"
    if days_remaining < duration * 7:
        return "SERREE"
    return "TENABLE"


def _success_rate(description_length: int, score: int, feasibility: str, coherence: str) -> float:
    """Produit un taux qualitatif borné et déterministe."""
    value = Decimal("0.9") - Decimal(max(0, score - 3)) * Decimal("0.04")
    if description_length < MIN_DESCRIPTION_FOR_CONFIDENCE:
        value -= Decimal("0.2")
    if feasibility == "SERREE":
        value -= Decimal("0.1")
    elif feasibility == "IRREALISTE":
        value -= Decimal("0.25")
    if coherence == "SOUS_ESTIME":
        value -= Decimal("0.1")
    return float(max(Decimal("0.1"), min(Decimal("0.95"), value)))


def _complexity_factors(signals: dict[str, int], description_length: int, days_remaining: int) -> list[str]:
    """Décrit les signaux ayant contribué au score."""
    factors = [f"Domaine détecté : {domain}" for domain in signals]
    if description_length > 180:
        factors.append("Périmètre décrit en détail")
    if days_remaining < 30:
        factors.append("Deadline très proche")
    return factors or ["Périmètre fonctionnel limité"]


def _risks(signals: dict[str, int], description_length: int, feasibility: str, coherence: str) -> list[dict]:
    """Construit des risques spécifiques aux signaux observés."""
    risks = []
    if "paiement" in signals:
        risks.append(("Conformité et fiabilité des paiements", 0.5, "ELEVEE", "Prévoir des tests d'intégration."))
    if "temps réel" in signals:
        risks.append(("Montée en charge des échanges temps réel", 0.5, "ELEVEE", "Tester la charge dès le prototype."))
    if description_length < MIN_DESCRIPTION_FOR_CONFIDENCE:
        risks.append(("Périmètre insuffisamment précisé", 0.8, "MOYEN", "Organiser un atelier de cadrage."))
    if feasibility != "TENABLE":
        risks.append(("Délai difficile à tenir", 0.7, "ELEVEE", "Réduire le périmètre ou renforcer l'équipe."))
    if coherence == "SOUS_ESTIME":
        risks.append(("Budget inférieur à la charge estimée", 0.8, "ELEVEE", "Réviser le budget ou le périmètre."))
    if not risks:
        risks.append(("Dépendances techniques à confirmer", 0.3, "MOYEN", "Valider les accès en cadrage."))
    return [
        {
            "description": description,
            "probabilite": probability,
            "impact": impact,
            "mitigation": mitigation,
        }
        for description, probability, impact, mitigation in risks
    ]


def _milestones(phases: list[dict]) -> list[dict]:
    """Crée un jalon à la fin de chaque phase."""
    week = 0
    milestones = []
    for phase in phases:
        week += phase["duree_semaines"]
        milestones.append({"nom": phase["nom"], "semaine": week})
    return milestones


def _budget_justification(coherence: str, amount: Decimal, recommended: Decimal) -> str:
    """Explique la comparaison budgétaire."""
    return f"Montant porteur {amount} EUR comparé à une estimation de {recommended} EUR."


def _deadline_justification(feasibility: str, days_remaining: int, duration: int) -> str:
    """Explique la faisabilité de la deadline."""
    return f"{days_remaining} jours restants pour environ {duration} semaines de travail."


def _positive_factors(signals: dict[str, int], description_length: int) -> list[str]:
    """Liste les facteurs favorables."""
    factors = ["Budget et durée explicitement fournis."]
    if description_length >= MIN_DESCRIPTION_FOR_CONFIDENCE:
        factors.append("Description suffisamment détaillée.")
    if signals:
        factors.append("Domaines techniques identifiables.")
    return factors


def _negative_factors(
    signals: dict[str, int],
    description_length: int,
    feasibility: str,
    coherence: str,
) -> list[str]:
    """Liste les facteurs défavorables."""
    factors = []
    if not signals:
        factors.append("Peu de domaines techniques identifiables.")
    if description_length < MIN_DESCRIPTION_FOR_CONFIDENCE:
        factors.append("Description courte ou vague.")
    if feasibility != "TENABLE":
        factors.append("Deadline contraignante.")
    if coherence == "SOUS_ESTIME":
        factors.append("Budget insuffisant.")
    return factors or ["Aucun facteur négatif majeur détecté."]
