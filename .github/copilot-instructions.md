# Instructions pour Copilot : projet Freelancy (module User)

## Contexte
- Backend : Django + Django REST Framework, Python 3.12, SQLite, modèle utilisateur personnalisé `users.User` (users/models.py).
- Frontend séparé : React (Vite), qui appelle uniquement l'API Django.
- Le LLM est appelé uniquement côté Django, via `call_llm` dans users/ai/llm_client.py. Ne jamais appeler un LLM depuis React.

## Règles obligatoires
- Aucune clé ni secret en dur : tout passe par les settings et le fichier .env.
- Avant tout appel au LLM, anonymiser les textes avec users/ai/anonymizer.py.
- La sortie du LLM est toujours validée (JSON et schéma) avant utilisation ou affichage.
- Gérer les erreurs LLMError (timeout, quota, configuration) sans faire planter l'API.
- Utiliser l'ORM Django (pas de SQL brut, pour éviter les injections).
- Docstring sur chaque fonction, commentaires en français, types explicites.
- Chaque nouvelle fonctionnalité est livrée avec des tests Django dans users/tests/.
- Ne pas modifier config/settings.py ni ajouter de dépendance sans me le signaler.
- Répondre en français.