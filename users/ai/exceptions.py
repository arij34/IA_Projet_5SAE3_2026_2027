"""Erreurs métier de la couche IA (pour les gérer proprement dans les vues)."""


class LLMError(Exception):
    """Erreur générique d'appel au LLM."""


class LLMConfigError(LLMError):
    """Configuration manquante ou invalide (clé API absente, fournisseur inconnu...)."""


class LLMTimeoutError(LLMError):
    """Le LLM n'a pas répondu à temps."""


class LLMQuotaError(LLMError):
    """Quota ou limite de requêtes dépassé."""


class LLMResponseError(LLMError):
    """Réponse du LLM inutilisable (HTTP en erreur, contenu vide...)."""
