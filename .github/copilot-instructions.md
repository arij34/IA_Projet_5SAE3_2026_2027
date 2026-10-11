# Instructions pour Copilot : Freelancy (front)

Projet : React + TypeScript + Vite. Commentaires et messages affichés en français.

## API (back Django REST, déjà terminé)
Les appels passent par le préfixe /api (proxy Vite vers http://127.0.0.1:8000).
- POST /api/auth/register/ : username, email, password, role (FREELANCER ou
  PROJECT_OWNER), title, bio, skills. Réponse 201 avec moderation_status.
- POST /api/auth/login/ : username, password. 200 => { token, user }.
  400 => identifiants invalides. 403 => { detail, moderation_status } si le
  profil n'est pas encore accepté (SUSPECT, PENDING ou REJETE).
- GET et PATCH /api/users/me/ : profil de l'utilisateur connecté.
- /api/admin/moderation/ : réservé au rôle ADMIN (liste, détail,
  POST .../<id>/approve/, DELETE .../<id>/).
- Authentification : en-tête "Authorization: Token <jeton>".
- Rôles : FREELANCER, PROJECT_OWNER, ADMIN.
- Statuts : PENDING, OK, SUSPECT, REJETE.

## Règles
- Types explicites, jamais de "any".
- Composants fonctionnels et hooks.
- Tous les appels HTTP passent par src/api/client.ts, jamais de fetch direct
  dans un composant.
- Toujours gérer les états : chargement, erreur, succès.
- Afficher les textes saisis par les utilisateurs comme du texte simple
  (jamais dangerouslySetInnerHTML).
- Jamais de clé API ni de secret dans le front. Le LLM n'est jamais appelé
  depuis React, seulement via l'API Django.