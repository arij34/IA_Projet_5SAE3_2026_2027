"""Registry of curated 20-question quizzes: (category slug, difficulty, title, payload)."""

from challenges.curated_quizzes_base import to_payload
from challenges.curated_quizzes_advanced import (
    DJANGO_ADVANCED,
    PYTHON_ADVANCED,
    REACT_ADVANCED,
    TYPESCRIPT_ADVANCED,
)
from challenges.curated_quizzes_new_categories import (
    GIT_ADVANCED,
    JAVASCRIPT_ADVANCED,
    SQL_ADVANCED,
)
from challenges.curated_quizzes_django import DJANGO_BEGINNER, DJANGO_INTERMEDIATE
from challenges.curated_quizzes_python import PYTHON_BEGINNER, PYTHON_INTERMEDIATE
from challenges.curated_quizzes_react import REACT_BEGINNER, REACT_INTERMEDIATE
from challenges.curated_quizzes_typescript import TYPESCRIPT_BEGINNER, TYPESCRIPT_INTERMEDIATE

QUESTIONS_PER_QUIZ = 20

_SOURCES = (
    ("python", "BEGINNER", PYTHON_BEGINNER),
    ("python", "INTERMEDIATE", PYTHON_INTERMEDIATE),
    ("django", "BEGINNER", DJANGO_BEGINNER),
    ("django", "INTERMEDIATE", DJANGO_INTERMEDIATE),
    ("react", "BEGINNER", REACT_BEGINNER),
    ("react", "INTERMEDIATE", REACT_INTERMEDIATE),
    ("typescript", "BEGINNER", TYPESCRIPT_BEGINNER),
    ("typescript", "INTERMEDIATE", TYPESCRIPT_INTERMEDIATE),
    ("python", "ADVANCED", PYTHON_ADVANCED),
    ("django", "ADVANCED", DJANGO_ADVANCED),
    ("react", "ADVANCED", REACT_ADVANCED),
    ("typescript", "ADVANCED", TYPESCRIPT_ADVANCED),
    ("javascript", "ADVANCED", JAVASCRIPT_ADVANCED),
    ("sql", "ADVANCED", SQL_ADVANCED),
    ("git", "ADVANCED", GIT_ADVANCED),
)

CURATED_QUIZZES = tuple(
    (slug, difficulty, title, to_payload(title, questions))
    for slug, difficulty, (title, questions) in _SOURCES
)

CURATED_ADVANCED_QUIZZES = tuple(
    item for item in CURATED_QUIZZES if item[1] == "ADVANCED"
)

CURATED_NEW_CATEGORY_QUIZZES = tuple(
    item for item in CURATED_QUIZZES if item[0] in {"javascript", "sql", "git"}
)
