"""Exceptions du client LLM de l'application projects."""


class LLMError(Exception):
    """Erreur de base du client LLM projects."""


class LLMConfigError(LLMError):
    """Configuration absente ou invalide du client LLM."""


class LLMTimeoutError(LLMError):
    """Le fournisseur LLM n'a pas répondu dans le délai imparti."""


class LLMQuotaError(LLMError):
    """Le quota du fournisseur LLM est dépassé."""


class LLMAuthError(LLMError):
    """L'authentification auprès du fournisseur LLM a échoué."""


class LLMServiceError(LLMError):
    """Le fournisseur LLM est momentanément indisponible."""


class LLMResponseError(LLMError):
    """La réponse du fournisseur LLM est absente ou mal formée."""
