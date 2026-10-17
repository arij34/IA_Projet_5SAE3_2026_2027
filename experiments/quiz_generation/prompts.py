"""Prompt conditions for the quiz-generation experiment (isolated from production).

Condition A is defined here. Condition B reuses the production prompt
(`quiz-gen-v1`) unchanged, imported from `challenges.services.generation`.
"""

BASELINE_VERSION = "quiz-baseline-v0"
PRODUCTION_VERSION = "quiz-gen-v1"

BASELINE_USER_TEMPLATE = (
    "Génère un quiz de {questions} questions à choix multiple sur {subject}, "
    "niveau {difficulty}. Chaque question a {choices} choix dont un seul est correct. "
    'Réponds en JSON avec ce format : {{"title": "...", "questions": [{{"text": "...", '
    '"choices": ["...", "...", "...", "..."], "correct_index": 0, "explanation": "..."}}]}}'
)


def build_baseline_messages(case: dict) -> list[dict]:
    """Condition A: no system prompt; subject name, level and counts only."""
    user = BASELINE_USER_TEMPLATE.format(
        subject=case["category_name"],
        difficulty=case["difficulty_label"],
        questions=case["question_count"],
        choices=4,
    )
    return [{"role": "user", "content": user}]


def build_production_messages(case: dict) -> list[dict]:
    """Condition B: the unmodified production prompt (quiz-gen-v1)."""
    from types import SimpleNamespace

    from challenges.services import generation

    category = SimpleNamespace(
        name=case["category_name"], description=case["category_description"]
    )
    return [
        {"role": "system", "content": generation.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": generation.build_user_prompt(category, case["difficulty"]),
        },
    ]


OBJECTIVE_VERSION = "quiz-objective-v2"

# Candidate C = production quiz-gen-v1 text (imported, unmodified) + experimental additions.
OBJECTIVE_SYSTEM_ADDENDUM = (
    " Contrairement au sujet, l'objectif d'apprentissage et la rubrique proviennent de "
    "l'application : ils sont contraignants. Aucun document de référence ne t'est fourni : "
    "ne prétends jamais en avoir consulté. Toute réponse correcte doit être soutenue par le "
    "concept technique pertinent et par la formulation exacte de la question. Vérifie que "
    "l'explication justifie la réponse marquée ; ne confonds pas des opérations ou concepts "
    "voisins, et n'invente ni méthode, ni comportement d'API, ni garantie technique. Si une "
    "question ne peut pas être formulée sans ambiguïté dans l'objectif fourni, remplace-la "
    "par une autre question dans cet objectif."
)

OBJECTIVE_USER_BLOCK = """

Objectif d'apprentissage (contrainte obligatoire) : {objective}
Rubrique (contraintes obligatoires) : {rubric}

Consignes supplémentaires :
- Les {questions} questions évaluent directement l'objectif d'apprentissage ci-dessus.
- Traite la rubrique comme des contraintes à respecter, pas comme un simple contexte.
- Évite les sujets voisins, sauf s'ils sont indispensables pour évaluer l'objectif.
- Chaque question a exactement une réponse défendable selon son libellé ; n'utilise pas
  « toutes les réponses ci-dessus » lorsque les choix se chevauchent ou dépendent d'hypothèses.
- Évite les conditions implicites qui pourraient rendre la réponse marquée fausse. Les
  distracteurs sont plausibles, distincts et non défendables comme réponses correctes.
- Vérifie que la réponse pointée par "correct_index" et l'explication concordent exactement.
- Respecte le format JSON exact et les {choices} choix distincts décrits plus haut.
- Si tu inclus du code, assure-toi qu'il est syntaxiquement plausible et illustre bien le
  concept demandé ; le bon index et l'explication doivent correspondre à ce code.
- Préfère un exemple précis à une affirmation vague sur les conséquences d'un comportement.
- Si le sujet concerne Django et les modèles, distingue l'instanciation (Model(...)), la
  persistance d'une instance avec .save(), et le raccourci de gestionnaire .objects.create()
  qui construit puis sauvegarde une instance. Ne présente pas .save() comme l'instanciation.
- Si le sujet concerne TypeScript et les unions discriminées, distingue une union de types
  d'objets variants partageant un discriminant à valeur littérale d'un seul type d'objet dont
  la propriété discriminante accepte plusieurs littéraux.
- Si le sujet concerne TypeScript et typeof, distingue l'opérateur JavaScript exécuté à
  l'exécution de l'analyse de flot de contrôle de TypeScript qui peut rétrécir un type statique
  à la compilation. Précise le niveau visé par la question.
- La rubrique peut mentionner des pages citées dont le contenu ne t'est pas fourni : \
applique-la au mieux de tes connaissances sans prétendre avoir consulté ces pages."""


def build_objective_messages(case: dict) -> list[dict]:
    """Condition C: quiz-gen-v1 plus the case learning objective and rubric."""
    from challenges.services import generation

    messages = build_production_messages(case)
    messages[0]["content"] = generation.SYSTEM_PROMPT + OBJECTIVE_SYSTEM_ADDENDUM
    messages[1]["content"] += OBJECTIVE_USER_BLOCK.format(
        objective=case["learning_objective"],
        rubric=case["rubric"],
        questions=case["question_count"],
        choices=generation.CHOICE_COUNT,
    )
    return messages


CONDITIONS = {
    "A": (BASELINE_VERSION, build_baseline_messages),
    "B": (PRODUCTION_VERSION, build_production_messages),
    "C": (OBJECTIVE_VERSION, build_objective_messages),
}
