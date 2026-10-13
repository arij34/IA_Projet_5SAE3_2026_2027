# Journal des prompts : module Project, partie front (Freelancy)

Suite du journal des prompts du projet Freelancy. Ce document reprend, dans
l'ordre, les demandes formulées pendant la séance et les résultats obtenus
dans le frontend React/TypeScript/Vite.

Méthode suivie : explorer le frontend et le contrat réel de l'API Django,
modifier uniquement le front, tester, puis corriger les comportements observés.
Outil de génération : GitHub Copilot (mode Agent dans VS Code), avec les
instructions persistantes dans `.github/copilot-instructions.md`.
Stack concernée : React, TypeScript, Vite, react-router-dom et lucide-react.

> Légende : [x] = réalisé et vérifié, [ ] = à confirmer.

---

## Entrée 1 : alignement du formulaire avec l'API des projets

### Prompt donné

Aligner le formulaire de création de projet sur `POST /api/projects/`, sans
modifier le backend. L'API attend exactement `name`, `description`, `deadline`
au format `AAAA-MM-JJ` et `estimated_amount` envoyé comme chaîne avec un point
décimal.

Demandes principales :

- renommer `title` en `name` ;
- renommer `date_limite` en `deadline` ;
- remplacer `budget_min` et `budget_max` par « Montant estimé » ;
- retirer `devise`, `duree_semaines` et `specialites` du formulaire et de la
  requête ;
- mettre à jour les types TypeScript ;
- refuser un montant vide, nul ou négatif ;
- convertir une virgule décimale en point ;
- afficher le message du backend sous le champ concerné ;
- ne modifier aucun autre fichier.

### Résultat

- [x] Le payload de création utilise uniquement les champs attendus par l'API.
- [x] Le montant est normalisé avec un point décimal.
- [x] Les montants vides, nuls ou négatifs sont refusés côté formulaire.
- [x] Les erreurs 400 sont associées aux champs concernés.
- [x] Les anciens champs non pris en charge par le backend ne sont plus envoyés.
- [x] Les types TypeScript concernés ont été adaptés.

---

## Entrée 2 : exploration initiale du frontend

### Prompt donné

Explorer `src/` et identifier les fichiers correspondant à :

- la page d'accueil ;
- le routeur ;
- le fichier d'appel à l'API des projets ;
- les types TypeScript des projets ;
- la page « Nouveau projet » ;
- le composant du résultat d'analyse.

Répondre avec les chemins exacts, sans modifier les fichiers.

### Résultat

Les fichiers frontend concernés ont été repérés, notamment :

- `src/App.tsx` pour les routes ;
- `src/api/projects.ts` pour les appels de l'API des projets ;
- `src/types/project.ts` pour les types ;
- `src/pages/NewProjectPage.tsx` pour le formulaire et l'analyse ;
- `src/pages/MyProjectsPage.tsx` pour la gestion des projets ;
- `src/pages/HomePage.tsx` et `src/components/Layout.tsx` pour l'accueil et
  la navigation.

---

## Entrée 3 : ajout de la gestion des projets

### Prompt donné

Ajouter une page de gestion des projets réservée aux utilisateurs
`PROJECT_OWNER`.

Demandes principales :

- ajouter le lien « Gestion de projet » ;
- créer la route `/gestion-projets` ;
- ajouter un bouton « Créer un projet » en haut à droite ;
- ouvrir le formulaire existant ;
- afficher la liste obtenue avec `GET /api/projects/` ;
- afficher le nom, le montant estimé, la date limite et le statut ;
- ajouter les actions modifier et supprimer ;
- gérer le chargement, la liste vide et les erreurs ;
- modifier avec `PATCH` ;
- désactiver la modification d'un projet `PUBLISHED` ;
- supprimer avec confirmation et gérer `204 No Content`.

### Résultat

- [x] La page [MyProjectsPage.tsx](../src/pages/MyProjectsPage.tsx) a été
  créée et reliée à la route `/gestion-projets`.
- [x] La liste des projets est chargée via `listProjects()`.
- [x] Les statuts sont affichés avec des libellés français et des badges.
- [x] Les boutons modifier et supprimer possèdent des libellés accessibles.
- [x] La suppression demande une confirmation et retire la ligne après succès.
- [x] La réponse `204` est gérée sans appel à `response.json()`.
- [x] Les états de chargement, de liste vide et d'erreur sont affichés.
- [x] La modification réutilise le formulaire existant.
- [x] Un projet `PUBLISHED` ne peut pas être modifié.

---

## Entrée 4 : déplacement de la navigation

### Prompt donné

Déplacer le bouton « Gestion de projet » de la section
« Prêt à lancer votre prochaine collaboration ? » vers le header, à côté du
profil. Le lien doit être visible uniquement pour un `PROJECT_OWNER`.
Supprimer le bouton « Créer un nouveau projet » du header, puisque la création
est déjà accessible depuis la page de gestion.

### Résultat

- [x] Le lien « Gestion de projet » est affiché dans le header.
- [x] Il est conditionné au rôle `PROJECT_OWNER`.
- [x] Le bouton de la section d'appel à l'action de l'accueil a été retiré.
- [x] L'ancien lien de création dans le header a été supprimé.
- [x] Le bouton de création reste disponible dans la page de gestion.

---

## Entrée 5 : correction de la page vide après publication

### Prompt donné

Après l'acceptation d'une analyse, la redirection vers
`/gestion-projets` affiche une page vide alors que l'API renvoie directement
un tableau JSON de projets. Corriger le frontend sans modifier le backend.

### Cause trouvée

Le frontend supposait principalement une réponse paginée avec une propriété
`results`, alors que la réponse réelle pouvait être un tableau direct :

```json
[
  {
    "id": 9,
    "name": "CloudMonitor",
    "deadline": "2026-10-31",
    "estimated_amount": "23.25",
    "status": "PUBLISHED"
  }
]
```

### Résultat

- [x] `listProjects()` accepte un tableau direct.
- [x] `listProjects()` continue également d'accepter `{ results: [...] }`.
- [x] La page de gestion consomme toujours un tableau normalisé.
- [x] Les projets publiés s'affichent après la redirection.

---

## Entrée 6 : publication et refus après analyse

### Prompt donné

Après l'analyse d'un projet :

- « Accepter la publication » appelle `/publish/` puis redirige vers
  `/gestion-projets` ;
- « Refuser » appelle `/decline/`, reste sur le formulaire et affiche
  « Projet refusé » ;
- les champs du formulaire sont conservés ;
- les deux boutons sont désactivés pendant l'appel ;
- une erreur 409 affiche un message adapté et recharge le projet.

### Résultat

- [x] La publication appelle l'endpoint attendu.
- [x] La redirection vers la gestion des projets est effectuée après succès.
- [x] Le projet publié apparaît avec le statut `PUBLISHED`.
- [x] Le refus conserve le formulaire et affiche le message demandé.
- [x] Les boutons sont désactivés pendant l'appel.
- [x] Les conflits `409` sont traités sans masquer l'erreur.

---

## Entrée 7 : amélioration générale de l'analyse IA

### Prompt donné

Améliorer la présentation du résultat de `POST /api/projects/<id>/analyze/`
sans modifier l'API, les appels API ou la logique de publication et de refus.

Demandes principales :

- afficher « Analyse simulée » si `simulated` vaut `true` ;
- afficher la complexité, la durée et le nombre de freelancers ;
- comparer le budget recommandé au montant estimé ;
- afficher la cohérence budgétaire ;
- afficher la confiance avec une barre de progression ;
- afficher les spécialités sous forme de pastilles ;
- séparer les risques et les jalons ;
- afficher les références utilisées ;
- rendre les longues sections repliables ;
- afficher une carte d'erreur avec « Réessayer » ;
- afficher un chargement pendant l'analyse ;
- rappeler « L'IA aide à décider, vous décidez ».

### Résultat

- [x] Le bandeau d'analyse simulée est conditionnel à `simulated`.
- [x] Les indicateurs de durée, d'équipe, de budget et de confiance sont
  affichés.
- [x] Les barres de progression portent un rôle ARIA.
- [x] Les valeurs de complexité sont converties en libellés français.
- [x] La cohérence du budget et la justification sont affichées.
- [x] La faisabilité de la deadline et l'indice de réussite sont affichés
  lorsqu'ils existent.
- [x] Les sections longues peuvent être repliées.
- [x] Les textes issus de l'API sont affichés comme texte simple.
- [x] Les champs absents ou vides n'entraînent pas d'écran blanc.

---

## Entrée 8 : correction de l'écran blanc après l'analyse

### Prompt donné

Le backend renvoie maintenant une réponse contenant :

```json
{
  "result": {},
  "simulated": true,
  "error": null,
  "analyzed_at": "..."
}
```

Adapter les types et le rendu pour les objets structurés :

- `Risk` avec `description`, `probabilite`, `impact` et `mitigation` ;
- `Milestone` avec `nom` et `semaine` ;
- `Specialty` avec `nom`, `nb`, `niveau` et `charge_pourcentage` ;
- `Phase` avec `nom`, `objectif`, `duree_semaines`, `livrables`,
  `specialites` et `budget_pourcentage`.

Ne jamais rendre directement un objet React et ajouter des gardes défensives.

### Cause exacte trouvée

Le frontend tentait auparavant de rendre directement des objets dans JSX,
notamment avec des expressions équivalentes à `{risk}` ou `{milestone}`.
React ne peut pas rendre directement ces objets, ce qui provoquait l'écran
blanc lorsque l'API renvoyait les nouveaux objets structurés.

### Résultat

- [x] Les interfaces `Risk`, `Milestone`, `Specialty` et `Phase` correspondent
  au contrat réel.
- [x] Les propriétés des risques sont rendues explicitement.
- [x] Les propriétés des jalons sont rendues explicitement.
- [x] Les propriétés des spécialités sont rendues explicitement.
- [x] Les propriétés des phases, livrables et spécialités sont rendues
  explicitement.
- [x] `response.result`, `response.error`, `response.simulated` et
  `response.analyzed_at` sont traités séparément.
- [x] Les tableaux absents sont remplacés par des tableaux vides uniquement
  pour l'affichage.
- [x] Le formulaire est conservé si l'analyse échoue.

---

## Entrée 9 : refonte du haut de la page d'analyse

### Prompt donné

Refondre la partie supérieure de la page d'analyse sans changer le backend,
les appels API ni la logique de publication ou de refus.

Demandes principales :

- bandeau ambre discret « Analyse simulée » ;
- titre « Résultat de l'analyse » ;
- badge de complexité avec libellé accentué ;
- score de complexité sur 10 ;
- grille responsive de quatre indicateurs ;
- durée et fourchette ;
- équipe ;
- budget recommandé ;
- confiance de l'IA ;
- jauge du budget avec repère du montant du porteur ;
- badges « Sous-estimé », « Réaliste » ou « Surestimé » ;
- carte deadline ;
- carte d'indice de réussite ;
- mention « estimation qualitative, pas une probabilité ».

### Résultat

- [x] L'en-tête présente le titre, la complexité et le score disponibles.
- [x] Les quatre cartes d'indicateurs sont responsives.
- [x] Les jauges sont accessibles et accompagnées de libellés.
- [x] Les valeurs inconnues ou absentes sont masquées ou remplacées par une
  présentation sûre.
- [x] Aucun emoji ni nouvelle bibliothèque n'a été ajouté pour cette refonte.

---

## Entrée 10 : refonte du bas de la page d'analyse

### Prompt donné

Refondre la partie inférieure de l'analyse :

- frise des phases proportionnelle à leur durée ;
- affichage vertical sur mobile ;
- détails repliables par phase ;
- ligne de temps des jalons ;
- risques triés par gravité ;
- probabilité et impact séparés ;
- mesures de mitigation sur leur propre ligne ;
- spécialités recommandées avec niveau et charge ;
- hypothèses et questions de clarification repliables ;
- recommandations ;
- références utilisées ;
- barre de décision ;
- squelette de chargement ;
- carte d'erreur avec bouton « Réessayer ».

### Résultat

- [x] Les phases sont présentées sous forme de frise et de cartes détaillées.
- [x] Les jalons sont ordonnés par semaine.
- [x] Les risques sont rendus propriété par propriété et triés.
- [x] Les spécialités affichent le nombre, le niveau et la charge lorsqu'ils
  existent.
- [x] Les hypothèses et questions peuvent être repliées.
- [x] Les recommandations et références sont affichées en texte simple.
- [x] La barre de décision conserve la logique de publication et de refus.
- [x] Les états de chargement et d'erreur sont pris en charge.

---

## Entrée 11 : ajout du chatbot RAG

### Prompt donné

Ajouter une interface de chatbot RAG pour les porteurs de projet via
`POST /api/projects/chatbot/`.

Contraintes et demandes :

- ajouter `ChatbotResponse` dans les types ;
- ajouter `askChatbot(question)` dans `projects.ts` ;
- réutiliser l'envoi du jeton existant ;
- créer une page ou un composant Assistant ;
- afficher les messages utilisateur et assistant ;
- ajouter un champ, un bouton d'envoi et un compteur ;
- reprendre exactement la longueur maximale du backend ;
- désactiver l'envoi pendant l'appel ;
- afficher les réponses en texte simple ;
- afficher les sources comme étiquettes ;
- afficher « Réponse simulée » si `simulated` vaut `true` ;
- gérer les erreurs 401, 403, 429, réseau et le champ `error` ;
- ne pas stocker la conversation dans `localStorage` ;
- protéger la page et le lien par le rôle `PROJECT_OWNER`.

### Résultat

- [x] Le type `ChatbotResponse` a été ajouté.
- [x] La constante `MAX_CHATBOT_QUESTION_CHARS` vaut `1000`, comme dans le
  backend.
- [x] `askChatbot()` utilise `apiFetch` et donc le jeton existant.
- [x] La page [AssistantPage.tsx](../src/pages/AssistantPage.tsx) a été créée.
- [x] La route `/assistant` a été ajoutée.
- [x] Le lien « Assistant » est visible uniquement pour les porteurs.
- [x] Le compteur de caractères et la limite de saisie sont présents.
- [x] Une question vide ou composée d'espaces désactive le bouton.
- [x] Les appels en cours désactivent le bouton et affichent un chargement.
- [x] Les réponses et les erreurs sont affichées en texte simple.
- [x] Les sources sont affichées comme identifiants, sans texte déduit.
- [x] Aucun stockage local ni secret n'a été ajouté.

---

## Entrée 12 : diagnostic du message d'indisponibilité du chatbot

### Prompt donné

Lors de l'envoi d'une question, le chatbot affiche :

> Le chatbot est momentanément indisponible.

Vérifier si le problème vient du frontend, du statut HTTP, du champ `error`
renvoyé par l'API ou de la configuration du fournisseur LLM. Ne pas ajouter
de clé API dans le frontend et ne pas modifier le backend sans autorisation.

### Analyse réalisée

Le code frontend traite correctement une réponse HTTP 200 contenant le champ
`error`. Le backend peut renvoyer, en cas d'échec du fournisseur LLM :

```json
{
  "answer": null,
  "sources": [],
  "simulated": false,
  "error": "..."
}
```

L'inspection du backend a montré que l'erreur est produite par
`call_chatbot_llm()`. Les causes possibles sont la configuration du
fournisseur, une clé serveur absente ou invalide, un quota dépassé, un modèle
indisponible ou une erreur réseau.

### Résultat

- [x] Le frontend n'appelle pas directement le fournisseur LLM.
- [x] Aucune clé API n'a été ajoutée au frontend.
- [x] Le champ `error` est traité sans afficher le détail technique brut.
- [x] Le problème visible est identifié comme un problème probable de
  configuration ou de disponibilité du service LLM côté backend.
- [ ] La cause exacte doit encore être confirmée avec le corps réel de la
  réponse dans l'onglet Network et les logs Django.

---

## Fichiers frontend principaux concernés

- `src/api/projects.ts`
- `src/types/project.ts`
- `src/pages/NewProjectPage.tsx`
- `src/pages/MyProjectsPage.tsx`
- `src/pages/AssistantPage.tsx`
- `src/App.tsx`
- `src/components/Layout.tsx`
- `src/pages/HomePage.tsx`
- `src/auth/AuthContext.tsx`

## Vérifications réalisées

- [x] Build frontend exécuté avec succès sur les changements concernés.
- [x] Lint ciblé des fichiers modifiés exécuté.
- [x] `git diff --check` exécuté.
- [x] Vérification de la normalisation de la liste des projets.
- [x] Vérification de la gestion de la réponse `204`.
- [x] Vérification du rendu des objets d'analyse sans objet React direct.
- [x] Vérification du traitement des réponses d'erreur du chatbot.
- [ ] Tests frontend automatisés : aucun jeu de tests frontend n'était présent
  dans le projet.

