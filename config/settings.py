"""
Django settings for config project.
Projet Freelancy - backend API
"""

import os
from pathlib import Path

from dotenv import load_dotenv
import sys  # noqa: E402

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Charge les variables du fichier .env (à côté de manage.py)
load_dotenv(BASE_DIR / ".env")


# --- Sécurité ---------------------------------------------------------------

# En production, définissez SECRET_KEY dans le fichier .env
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-key-a-changer-en-production",
)

# DEBUG=True dans .env en développement
DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Librairies tierces
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    # Applications du projet
    "users",
    "projects",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # doit rester tout en haut
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Base de données --------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# --- Utilisateur personnalisé ----------------------------------------------
AUTH_USER_MODEL = "users.User"


# --- Validation des mots de passe ------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# --- Internationalisation ---------------------------------------------------

LANGUAGE_CODE = "fr"

TIME_ZONE = "Africa/Tunis"

USE_I18N = True

USE_TZ = True


# --- Fichiers statiques -----------------------------------------------------

STATIC_URL = "static/"
PRIVATE_MEDIA_ROOT = Path(
    os.getenv("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media"))
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Django REST Framework --------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
}


# --- CORS (autorise le frontend React) -------------------------------------

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


# --- E-mail (affiché dans le terminal en développement) ---------------------

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- Configuration LLM (valeurs lues dans .env) -----------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")  # "mock", "anthropic" ou "gemini"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
COACH_MODEL_NAME = os.getenv("COACH_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))

# --- Client LLM de projects ------------------------------------------------

PROJECT_LLM_PROVIDER = os.getenv("PROJECT_LLM_PROVIDER", "")
PROJECT_LLM_API_KEY = os.getenv("PROJECT_LLM_API_KEY", "")
PROJECT_LLM_MODEL = os.getenv("PROJECT_LLM_MODEL", "")
PROJECT_ANALYSIS_THROTTLE_RATE = os.getenv(
    "PROJECT_ANALYSIS_THROTTLE_RATE",
    "10/hour",
)

if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]