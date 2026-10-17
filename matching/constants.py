"""Constantes et réglages par défaut du moteur de matching.

Toutes les valeurs sont surchargeables dans les réglages Django sans modifier
le code, via les noms préfixés par ``MATCHING_``.
"""

ALGORITHM_VERSION = "matching-v1"

# Poids initiaux des sous-scores déterministes (somme = 1).
DEFAULT_WEIGHTS = {
    "skills": 0.40,
    "budget": 0.20,
    "level": 0.15,
    "quiz": 0.25,
}

# Part du score sémantique IA dans le score final hybride.
DEFAULT_SEMANTIC_WEIGHT = 0.25

# Hypothèses de charge utilisées pour convertir un budget en tarif horaire.
DEFAULT_HOURS_PER_WEEK = 35.0
DEFAULT_ENGAGEMENT_RATIO = 0.5

# Tolérance de dépassement du tarif horaire avant un sous-score budget nul.
DEFAULT_BUDGET_TOLERANCE = 0.5

# Atténuation appliquée à un score de quiz hors spécialité demandée.
DEFAULT_QUIZ_INDIRECT_FACTOR = 0.8

# Score global minimal pour qu'un candidat soit retenu sur un poste d'équipe.
# En dessous, le poste reste non pourvu et le meilleur candidat écarté est
# tout de même restitué : aucun profil n'est supprimé silencieusement.
DEFAULT_TEAM_MIN_SCORE = 40.0

# Sous-score de compétences minimal pour considérer qu'un poste attribué est
# réellement couvert par les compétences déclarées du freelance.
DEFAULT_TEAM_MIN_SKILL_SCORE = 50.0

# Seuils d'inférence du niveau d'un freelance.
QUIZ_LEVEL_THRESHOLDS = ((80.0, "SENIOR"), (55.0, "CONFIRME"))
RATE_LEVEL_THRESHOLDS = ((70.0, "SENIOR"), (40.0, "CONFIRME"))

LEVELS = ("JUNIOR", "CONFIRME", "SENIOR")

# Score du critère niveau selon l'écart entre niveau requis et niveau estimé.
# Clé : (niveau estimé - niveau requis) en nombre de crans.
LEVEL_GAP_SCORES = {
    0: 100.0,
    1: 75.0,
    2: 55.0,
    -1: 55.0,
    -2: 25.0,
}

MIN_SCORE = 0.0
MAX_SCORE = 100.0
