# Journal des prompts : module User, partie front (Freelancy)

Suite de `journal-prompt-users.md` (partie back). Ici : les interfaces React qui
appellent l'API Django déjà terminée.

Méthode suivie (séance 3) : spécifier (contexte, objectif, contraintes, format),
générer, tester, relire, itérer.
Outil de génération : GitHub Copilot (mode Agent dans VS Code), avec des
instructions persistantes dans `.github/copilot-instructions.md`.
Stack : React, TypeScript, Vite, react-router-dom, lucide-react (icônes).

> Légende : [x] = fait et réussi, [ ] = à faire ou à confirmer.
> Une case n'est cochée que si le test ou la relecture a vraiment été fait.

## Périmètre de mon module
Freelancy est une plateforme IA qui met en relation des porteurs de projet et
des freelances. Mon travail :
- détection automatique des faux profils (modération IA + validation par un
  administrateur) ;
- suggestions d'amélioration des profils (tâche B, à faire).

Réalisés par mes collègues, hors de ce journal : matching intelligent entre
porteurs de projet et freelances, analyse de projet par l'IA (durée, budget),
planning de projet, challenges et blog. La page d'accueil les présente, mais
sans lien tant que leurs pages ne sont pas intégrées.

---

## Entrée 1 : instructions persistantes et structure du projet

### Instructions persistantes (system prompt du projet)
Fichier `.github/copilot-instructions.md` écrit à la main, avec :
- les routes de l'API (inscription, connexion, `/me`, API admin), le format
  de l'en-tête `Authorization: Token <jeton>`, les rôles et les statuts de
  modération ;
- les règles : types explicites (pas de `any`), composants fonctionnels,
  tous les appels HTTP via `src/api/client.ts`, gestion des états
  (chargement, erreur, succès), textes utilisateurs affichés comme du texte
  simple (jamais `dangerouslySetInnerHTML`), aucun secret dans le front, LLM
  jamais appelé depuis React.

### Prompt de structure (résumé)
- installer `react-router-dom` ;
- proxy de développement dans `vite.config.ts` (`/api` vers
  `http://127.0.0.1:8000`) pour éviter les problèmes CORS ;
- `src/types.ts` (Role, ModerationStatus, User), `src/auth/tokenStorage.ts`
  (getToken, setToken, clearToken avec try/catch) ;
- `src/api/client.ts` : `apiFetch<T>` qui ajoute le jeton, gère la réponse
  204 et lève une `ApiError` (status, data) ;
- pages vides et routes `/register`, `/login`, `/profile`,
  `/admin/moderation` ; suppression du contenu de démo de Vite.

### Résultat
`npm run lint`, `npm run build` et `npm run dev` passent ; les pages vides
s'affichent aux bonnes adresses.

---

## Entrée 2 : formulaire d'inscription

### Prompt (résumé)
Champs : nom d'utilisateur, email, mot de passe et confirmation, rôle
(FREELANCER ou PROJECT_OWNER seulement), titre, biographie, compétences
(séparées par des virgules, transformées en tableau). Contraintes :
- vérification locale (mots de passe identiques, champs obligatoires) ;
- appel via `apiFetch`, la confirmation du mot de passe n'est pas envoyée ;
- bouton désactivé pendant l'appel (anti double envoi) et message
  « Vérification de votre profil en cours... » car l'IA peut être lente ;
- erreurs 400 du back affichées sous chaque champ ;
- à la réception du 201, message selon `moderation_status` : OK (compte
  validé), SUSPECT ou PENDING (en cours de vérification), REJETE (refusé) ;
- aucune connexion automatique et aucun jeton stocké après l'inscription.

### Tests dans le navigateur (front et back démarrés)
- Inscription avec titre et bio : message « Votre profil est en cours de
  vérification par un administrateur. » Résultat attendu et obtenu. Ce n'est
  pas un échec : en mode `mock`, le faux LLM répond OK avec une confiance de
  0,5, et le service refuse l'OK sous 0,7, donc tout profil avec du texte
  devient SUSPECT.
- Journal du back : deux inscriptions réussies (201) et une refusée (400).
- Cas d'erreur vérifiés :
  - [x] mots de passe différents : message d'erreur, pas d'appel au back
  - [x] champs obligatoires vides : message d'erreur, pas d'appel au back
  - [x] email déjà utilisé : erreur 400 affichée sous le champ
  - [x] mot de passe trop faible : erreur 400 affichée sous le champ
  - [x] aucun jeton dans Local Storage après l'inscription

---

## Entrée 3 : page de connexion

### Prompt (résumé)
Champs nom d'utilisateur et mot de passe, appel de `POST /api/auth/login/`
via `apiFetch`. Réponse 200 : jeton enregistré avec `setToken`, redirection
vers `/admin/moderation` si le rôle est ADMIN, sinon vers `/profile`.
Messages en français selon la réponse du back :
- 400 : « Identifiants invalides. » ;
- 403 avec SUSPECT ou PENDING : « Votre profil est en cours de vérification
  par un administrateur. » ;
- 403 avec REJETE : « Votre profil a été refusé. » ;
- autre erreur : message général. Messages dans un élément `role="alert"`.

### Tests dans le navigateur
Journal du back après les essais : connexion valide (200) avec redirection
vers `/profile`, mauvais identifiants (400), compte SUSPECT refusé (403).
Les trois réponses du back sont bien gérées par le front.
- [x] `npm run lint` : sans erreur
- [x] `npm run build` : sans erreur
- [x] champs vides : aucun appel au back
- [x] jeton visible dans Local Storage après une connexion valide
- [x] connexion avec le compte admin créé depuis `/admin/` : redirection vers
      `/admin/moderation`

---

## Entrée 4 : page de profil

### Prompt (résumé)
- au chargement : redirection vers `/login` sans jeton ; `GET /api/users/me/`
  via `apiFetch`, affichage de « Chargement... » pendant l'appel ; sur 401 ou
  403, `clearToken()` puis redirection vers `/login` ; autre erreur : message
  en français avec `role="alert"` ;
- affichage en lecture seule (nom, email, rôle en français, statut de
  modération en texte) et formulaire modifiable (titre avec `maxLength` 120,
  bio, compétences séparées par des virgules, tarif horaire >= 0 optionnel),
  chaque champ avec un `<label>` relié à son input ;
- `PATCH /api/users/me/` avec seulement `title`, `bio`, `skills` et
  `hourly_rate` ; bouton désactivé et texte « Enregistrement et vérification
  en cours... » pendant l'appel ;
- si la réponse n'a pas `moderation_status = OK` (l'IA a repassé le profil en
  SUSPECT ou REJETE après modification) : `clearToken()`, message explicatif
  à la place du formulaire et lien vers `/login` ;
- erreurs 400 sous chaque champ (objet `{ champ: [messages] }`), bouton
  « Se déconnecter » ;
- règles de sécurité répétées : types explicites, pas de `any`, pas de
  `dangerouslySetInnerHTML`, le mot de passe n'apparaît jamais dans la page.

### Résultat
- [x] `npm run lint` : sans erreur
- [x] `npm run build` : sans erreur
- [x] affichage du profil après connexion
- [x] modification du tarif seul : « Profil enregistré. » (si le statut reste OK)
- [x] modification de la bio : profil repassé en vérification, déconnexion,
      message affiché (comportement attendu en mode `mock`)
- [x] reconnexion refusée avec le profil SUSPECT
- [x] tarif négatif : erreur affichée sous le champ
- [x] accès à `/profile` sans connexion : redirection vers `/login`
- [x] bouton « Se déconnecter » : retour sur `/login`, jeton supprimé

---

## Entrée 5 : écran admin de modération

### Prompt (résumé)
Page `/admin/moderation` réservée aux administrateurs, avec les routes de
l'API admin lues dans `.github/copilot-instructions.md` (Copilot ne doit pas
inventer de route) :
- redirection vers `/login` sans jeton ; 401 : `clearToken()` et retour à
  `/login` ; 403 : « Accès réservé aux administrateurs. » ;
- tableau des profils (nom, email, rôle, titre, statut en français) ;
- filtre par statut, par défaut SUSPECT et PENDING ;
- « Voir le détail », « Accepter » (mise à jour de la ligne sans recharger),
  « Supprimer » (confirmation, puis ligne retirée, réponse 204 gérée) ;
- erreurs d'action affichées avec `role="alert"` sans casser la liste.

### Résultat
- [x] la page s'affiche avec le filtre par défaut et le profil SUSPECT `test1`
- [ ] `npm run lint` : sans erreur
- [ ] `npm run build` : sans erreur
- [ ] « Voir le détail » : bio, compétences, tarif affichés
- [ ] « Accepter » : la ligne disparaît du filtre, le profil se reconnecte
      ensuite sur `/profile`
- [ ] « Supprimer » : confirmation, puis ligne retirée
- [ ] un utilisateur non admin sur `/admin/moderation` : « Accès réservé »

---

## Entrée 6 : design du front (page par page)

### Méthode
Le design est fait après la logique, sur une branche séparée (`front-design`),
page par page, avec un commit après chaque page testée. Règle répétée dans
chaque prompt : ne pas changer la logique (mêmes appels, messages,
redirections, `role="alert"`, `<label>`), seulement la structure HTML et les
classes CSS. CSS simple avec variables, icônes `lucide-react`, animations en
CSS et hook `useReveal` (IntersectionObserver), `prefers-reduced-motion`
respecté.

### Page d'accueil
- Prompt 1 : base de design (variables CSS, classes réutilisables), composant
  `Layout` (header, footer), page `HomePage` avec présentation de la
  plateforme (détection des faux profils, suggestions d'amélioration,
  matching, analyse de projet, challenges, blog), sans lien vers des pages
  inexistantes.
- Prompt 2 : design jugé trop basique ; ajout d'un header collant avec menu
  burger, d'un footer, d'icônes, d'animations et d'effets de défilement.
- Prompt 3 (corrections après relecture de la capture d'écran) :
  - texte du bouton d'inscription illisible (couleur écrasée par le style
    des liens du menu) : corrigé, libellés « S'inscrire » / « Se connecter » ;
  - section « Comment ça marche » étendue à 5 étapes (profil, vérification,
    matching, planning, challenges) ;
  - section finale « Prêt à commencer ? » refaite (collée à gauche et
    étroite : centrée dans un conteneur).
- [x] page d'accueil terminée
- [ ] `npm run lint` et `npm run build` sans erreur
- [ ] menu et section finale adaptés à l'état connecté ou non connecté

### Pages connexion, inscription, profil, admin
Un seul prompt pour les 4 pages (gain de temps), avec la même règle « ne pas
changer la logique ». Risque connu : une erreur est plus difficile à localiser
qu'avec un prompt par page.
- [ ] connexion : design appliqué, tous les cas de test refaits
- [ ] inscription : design appliqué, tous les cas de test refaits
- [ ] profil : design appliqué, tous les cas de test refaits
- [ ] admin : design appliqué, tous les cas de test refaits
- [ ] version mobile vérifiée sur les 4 pages

---

## Relecture : ce que j'ai vérifié dans le code
- Les réponses du back (200, 400, 403) vues dans le journal du serveur
  correspondent aux messages affichés par le front.
- Relecture de `ProfilePage.tsx` :
  - [x] aucun `fetch` direct : seulement `apiFetch` de `client.ts`
  - [x] aucun `any`
  - [x] aucun `dangerouslySetInnerHTML`
  - [x] aucun mot de passe affiché ni stocké
  - [x] le PATCH n'envoie que `title`, `bio`, `skills`, `hourly_rate`
  - [x] le jeton est supprimé quand le statut n'est plus OK
- Relecture de `AdminModerationPage.tsx` :
  - [ ] aucun `fetch` direct, aucun `any`, aucun `dangerouslySetInnerHTML`
  - [ ] textes des utilisateurs (bio, titre, compétences) affichés en texte
        simple
- Relecture après le design :
  - [ ] la logique des pages n'a pas changé (comparaison avec le commit
        précédent : `git diff`)

## Points de vigilance dans les prompts
- Le front traduit chaque réponse du back en un message précis pour
  l'utilisateur : chaque prompt liste les codes (201, 400, 403) et le texte
  attendu.
- Les règles de sécurité sont écrites dans les instructions persistantes et
  répétées dans les prompts (pas de HTML injecté, pas de secret, pas de mot
  de passe conservé).
- Un prompt par page, suivi de `npm run lint`, `npm run build` et d'un test
  réel dans le navigateur avec le back démarré.
- Le prompt de l'écran admin demande à Copilot de lire les routes dans le
  fichier d'instructions et de signaler ce qui manque, au lieu de les inventer.
- Pour le design : « ne change pas la logique » écrit dans chaque prompt.
- Le proxy Vite évite de configurer CORS pour le développement.

## Limites connues
- Le jeton est conservé dans `localStorage` : il serait lisible par un script
  injecté (faille XSS). Compromis accepté pour ce projet ; une alternative
  serait un cookie HttpOnly côté Django.
- Pas de tests automatiques du front : les tests sont faits à la main dans le
  navigateur.
- Le statut REJETE n'a pas pu être produit avec le LLM en mode `mock` ; il
  n'a pas été testé de bout en bout.
- Les fonctionnalités de mes collègues (matching, analyse de projet,
  planning, challenges, blog) ne sont pas encore reliées au front : la page
  d'accueil les présente sans lien.

## Enseignements
- Le front dépend de l'API réelle : construire le back d'abord a évité de
  refaire les formulaires.
- Un résultat qui ressemble à un échec peut être normal : le mode `mock`
  explique pourquoi un profil avec du texte devient SUSPECT.
- Un prompt trop chargé fait perdre du temps : découper en petites étapes
  (structure, inscription, connexion, profil) avec un test après chacune
  rend le travail plus facile à contrôler.
- Il faut tester les cas d'erreur, pas seulement le cas qui marche.
- Le code généré par Copilot reste sous ma responsabilité : relecture avec la
  checklist de la séance 3 avant chaque commit (zero trust).
- Séparer la logique et le design : le design vient après les tests, sur une
  branche à part, ce qui permet de revenir en arrière.
- Relire le résultat visuel sur une capture : l'IA a laissé un bouton sans
  texte visible et une section mal centrée, que seul un contrôle humain a vus.
- Le premier design généré est souvent trop basique : il faut itérer avec des
  remarques précises (un défaut par point).