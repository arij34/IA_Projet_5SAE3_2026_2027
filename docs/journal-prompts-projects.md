# Journal des prompts : module Projects (gestion de projets freelance)

Méthode suivie (séance 3) : spécifier, générer, tester, relire, itérer.
Outil de génération : GitHub Copilot (mode Agent), avec des instructions
persistantes dans `.github/copilot-instructions.md` (back et front).
Branche de travail : `project_module`, séparée du module Users.

Scénario : un porteur de projet crée un projet (nom, description, date
limite, montant estimé). Un modèle IA (Claude, via une clé API) analyse le
projet : budget estimé, nombre de freelancers, spécialités, durée, complexité,
risques, jalons. **L'IA aide à décider, le porteur décide** : il publie ou non
le projet. Les projets publiés apparaissent dans une liste. Un **assistant
projet** (chat, RAG sur la FAQ et les analyses) répond aux questions des
utilisateurs (Entrée 14).

Statuts : `DRAFT` → `ANALYZED` → `PUBLISHED` ou `DECLINED`.

Choix d'architecture actuel : `PROJECT_LLM_PROVIDER` est réservé à l'analyse
de projet (`mock` ou `anthropic`) et `CHATBOT_LLM_PROVIDER` est réservé au
chatbot (`mock` ou `gemini`). Le client Anthropic et les exceptions métier de
`projects` restent propres au module. Le chatbot réutilise explicitement
`users.ai.llm_client._call_gemini` pour éviter un second client Gemini. Le mode
`mock` est la valeur par défaut des deux fonctionnalités et ne fait aucun
appel réseau.

Lien avec le cours :
- Séance 3 (génération de code) : méthode spécifier, générer, tester, relire,
  itérer ; checklist de relecture ; instructions persistantes.
- Séance 4 (adaptation et optimisation) : **RAG** (Entrées 11 et 14).
  Le module `users` couvre la quantization et le pruning (journal Users,
  Entrée 5).

Plan de chaque entrée : prompt initial, résultat généré, tests appliqués,
résultats des tests, relecture, prompts de correction, résultats après
correction, limites, enseignements.

Bilan global au 13/10/2026 : `python manage.py test` :
**297 tests OK**. Les tests couvrent le CRUD, l'analyse, la validation des
réponses LLM, l'anonymisation, le RAG, le chatbot, la séparation des
fournisseurs et les erreurs Gemini. Les mentions « À COMPLÉTER » plus bas sont
des notes historiques des premières itérations ; elles ne décrivent pas
l'état final et sont récapitulées dans la section « État final vérifié ».

---

## Entrée 0 : instructions persistantes (`.github/copilot-instructions.md`)

### Contenu
Règles : types explicites, aucune clé API dans le code ni les logs, réponse
LLM = donnée non fiable validée avant usage et affichée en texte simple,
erreurs externes converties en exceptions du module, tests sans réseau,
vérification de l'authentification ET de la propriété, « ne modifie aucun
fichier non cité », « si un test échoue, signale-le ».

### Enseignements
- Des règles écrites une fois pour toutes évitent de répéter les mêmes
  consignes de sécurité dans chaque prompt.

---

## Entrée 1 : squelette de l'application `projects`

### Contexte
Créer le dossier `projects/` avec la même structure que `users/` :
`migrations/`, `ai/`, `services/`, `tests/` (avec `__init__.py`), sans
`tests.py`.

### Prompt initial
```
CONTEXTE : projet Django/DRF décrit dans .github/copilot-instructions.md.
L'application `users` sert de modèle de structure (#file:users/apps.py
#file:users/admin.py #file:users/urls.py).

OBJECTIF : créer le squelette de l'application `projects`, sans aucun modèle
ni logique métier.

CONTRAINTES :
- Dossier projects/ avec : __init__.py, apps.py (ProjectsConfig), admin.py,
  models.py, serializers.py, views.py, urls.py, permissions.py.
- Sous-dossiers, chacun avec son __init__.py : migrations/, ai/, services/,
  tests/.
- Ne crée PAS de fichier tests.py : le dossier tests/ le remplace.
- Ajouter "projects" dans INSTALLED_APPS (settings.py) et inclure
  projects.urls sous le préfixe api/ dans le urls.py principal.
- Fichiers vides ou avec seulement un docstring de module : aucun modèle,
  aucune vue, aucun endpoint à ce stade.

FORMAT : liste des fichiers créés et des deux fichiers modifiés
(settings.py, urls.py). Ne modifie aucun autre fichier.
```

### Résultat généré
- Fichiers créés : `__init__.py`, `apps.py`, `admin.py`, `models.py`,
  `serializers.py`, `views.py`, `urls.py`, `permissions.py`, et les dossiers
  `migrations/`, `ai/`, `services/`, `tests/` (chacun avec `__init__.py`).
- Fichiers modifiés : `config/settings.py` (`"projects"` dans
  `INSTALLED_APPS`, ligne 48) et `config/urls.py`
  (`path("api/", include("projects.urls"))`, ligne 30).

### Tests appliqués
```text
dir projects
python manage.py check
```

### Résultats des tests
- Aucun fichier `tests.py` créé (confirmé avec `dir projects`).
- `python manage.py check` : aucun problème.

### Relecture : problèmes constatés
1. Aucun défaut sur la structure : fichiers demandés présents, pas de
   `tests.py`, seuls `settings.py` et `urls.py` modifiés. La relecture n'a
   rien révélé, et je le note tel quel.

### Prompt de correction
- Aucun : pas de correction nécessaire.

### Limite connue
- `check` valide que les modules s'importent, pas leur comportement : les
  tests commencent à l'Entrée 2.
- La vérification a été faite après coup, quand le dossier contenait déjà le
  travail des étapes suivantes : elle confirme la structure finale, pas
  l'état exact juste après ce prompt.

### Enseignements
- Préciser « ne crée pas `tests.py` » et « un `__init__.py` par dossier »
  évite deux erreurs classiques de structure Django.
- Donner la structure de `users` avec `#file:` fournit un modèle concret à
  Copilot au lieu de le laisser inventer.

---

## Entrée 2 : modèle Project et CRUD

### Contexte
Modèle `Project` (owner, name, description, deadline, estimated_amount,
status) et endpoints CRUD réservés au porteur de projet.

### Prompt initial
```
CONTEXTE : projet Django/DRF décrit dans .github/copilot-instructions.md.
Application `projects` (squelette créé). Le modèle User existe déjà
(#file:users/models.py) avec un champ `role` (PROJECT_OWNER, FREELANCER, ADMIN).

OBJECTIF : créer le modèle Project et son CRUD.

CONTRAINTES :
- Modèle Project : owner (FK User), name (max 150), description (max 3000),
  deadline (date), estimated_amount (Decimal > 0), status (DRAFT, ANALYZED,
  PUBLISHED, DECLINED, défaut DRAFT), created_at, updated_at.
- Constantes MAX_NAME_CHARS et MAX_DESCRIPTION_CHARS, pas de nombres magiques.
- Endpoints : POST/GET /api/projects/, GET/PATCH/DELETE /api/projects/<id>/.
- Pas de PUT. Le client ne peut jamais envoyer `status` ni `owner`.
- Validation : deadline strictement dans le futur, montant > 0, nom non vide.
- Seul un PROJECT_OWNER authentifié peut créer. Un porteur ne voit, ne modifie
  et ne supprime que SES projets (404 sinon, pas 403).
- Si description, deadline ou estimated_amount change, le statut repasse à DRAFT.

FORMAT : code complet avec docstrings, migration, et tests dans
projects/tests/test_projects_crud.py : cas valides ET cas d'attaque (FREELANCER
qui crée, accès au projet d'un autre, `status` envoyé dans le POST, deadline
passée, montant négatif, changement de description qui remet en DRAFT).
Ne modifie aucun autre fichier.
```

### Résultat généré
- Modèle `Project`, serializers, vues, `permissions.py`, migration
  `0001_initial`, et `projects/tests/test_projects_crud.py` (10 tests).

### Tests appliqués
```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test projects.tests.test_projects_crud --verbosity 2
python manage.py test projects
python manage.py test
git --no-pager grep -n "def test_" projects/tests/test_projects_crud.py
git --no-pager grep -n "MAX_NAME_CHARS\|MAX_DESCRIPTION_CHARS\|read_only\|IsApprovedUser" projects/
git --no-pager grep -n "def get_queryset\|owner=" projects/views.py
git --no-pager grep -n "IsApprovedUser" projects/
```

### Résultats des tests (avant correction, 12/10/2026)
- `check` et `makemigrations --check --dry-run` : aucun problème.
- Tests CRUD : 10 tests, **9 OK, 1 échec** :
  `test_description_change_resets_status_to_draft` (400 au lieu de 200).
- Suite complète : 237 tests, 4 échecs, tous dans `projects` ; les 166 tests
  de `users` passent.

### Relecture : problèmes constatés
1. **Test de retour à DRAFT en échec** : le PATCH renvoyait 400, donc la
   règle « une modification de description remet le projet en DRAFT » n'était
   pas vérifiée. L'hypothèse d'une date limite codée en dur est **écartée** :
   le fichier de tests utilise `date.today() + timedelta(...)` (lignes 44 et
   58). Cause exacte : **À COMPLÉTER** (non relevée avant la correction ;
   relire le corps de la réponse 400 ou le diff de la correction).
2. **Contrôles du code (grep, 12/10/2026)** : `MAX_NAME_CHARS = 150` et
   `MAX_DESCRIPTION_CHARS = 3000` sont des constantes (`models.py`) utilisées
   par le serializer ; `owner` et `status` sont dans `read_only_fields`
   (`serializers.py`, ligne 27) ; les vues filtrent sur `owner=request.user`
   (`views.py`, lignes 51, 91 et 136), ce qui donne le 404 demandé. Ces
   numéros de ligne ont changé depuis : `views.py` a grandi (voir point 5).
3. **Trous dans les tests**, visibles dans les noms des 10 tests : aucune
   borne (150/151, 3000/3001), aucun nom composé d'espaces, aucun `owner`
   envoyé dans le POST, aucun `status` ou `owner` dans le PATCH, aucun test
   « le seul `name` ne remet pas en DRAFT », aucune requête sans jeton (401),
   aucun test de la deadline de demain acceptée.
4. **Duplication** : les valeurs 150 et 3000 existent aussi dans
   `sanitizer.py` (`MAX_NAME_CHARS_LLM`, `MAX_DESCRIPTION_CHARS_LLM`).
   Volontaire (limite d'envoi au LLM), mais à garder cohérent.
5. **Permission des vues** (greps et lecture de `views.py`, 13/10/2026) :
   `IsApprovedUser` n'a que deux occurrences dans `projects/` : l'import
   (ligne 24) et **un seul usage**, ligne 262, dans `PublishedProjectListView`
   (la liste publique). Les vues du porteur utilisent une autre permission,
   `IsProjectOwner` : `ProjectListCreateView` (liste et création),
   `ProjectDetailView`, `ProjectAnalyzeView`, `ProjectChatbotView` et
   `ProjectDecisionView` portent toutes `permission_classes =
   (IsProjectOwner,)`. La règle de `users` (compte accepté) n'est donc pas
   écrite dans ces vues : elle n'existe que si `IsProjectOwner`
   (`permissions.py`, non lu) l'inclut. **À COMPLÉTER** : `Get-Content
   projects\permissions.py -Encoding UTF8`, et dire si `IsProjectOwner` teste
   le rôle seul ou aussi `moderation_status`. Les numéros de lignes du point 2
   ne sont plus valables (le fichier a grandi d'environ 100 lignes depuis le
   12/10).
6. **Retour à DRAFT : défaut confirmé par lecture** (`serializers.py`,
   13/10/2026). La méthode `update` fait `tracked_fields = {"description",
   "deadline", "estimated_amount"}` puis `if
   tracked_fields.intersection(validated_data): validated_data["status"] =
   Project.Status.DRAFT`. Le test porte sur la **présence** des champs dans les
   données envoyées, pas sur un changement de valeur : un PATCH qui renvoie la
   même description remet le projet en DRAFT (et lui fait perdre son statut
   ANALYZED), alors que le prompt dit « si ... change ». Réserve : les 55
   premières lignes du fichier n'ont pas été lues. Deuxième défaut dans la même
   méthode : l'ensemble de trois champs est écrit deux fois (dans le verrou
   « projet publié » et dans `tracked_fields`), ce qui viole la règle DRY de la
   checklist. Le verrou est une règle que le prompt de l'Entrée 2 ne demandait
   pas : un projet publié refuse la modification de ces champs
   (`ValidationError`), testé par `test_published_project_cannot_change_business_fields`
   (Entrée 6).
7. **Contrôles par lecture de `views.py` (13/10/2026)** : les deux
   `get_queryset` (`ProjectListCreateView` et `ProjectDetailView`) filtrent sur
   `owner=self.request.user`, ce qui produit le 404 demandé pour le projet d'un
   autre ; `perform_create` fixe le propriétaire (`serializer.save(owner=...)`) ;
   `ProjectDetailView` limite les méthodes à `get`, `patch`, `delete`, `head`,
   `options` (pas de PUT) ; la création ne journalise que les noms des champs
   invalides (`sorted(serializer.errors.keys())`), pas leur contenu.

### Prompt de correction
- **À COMPLÉTER** : prompt réellement envoyé à Copilot pour corriger le test
  de retour à DRAFT (avec le corps de la réponse 400).
- Prompt de complément pour les trous du point 3 :
```
Ajoute dans projects/tests/test_projects_crud.py les tests suivants :
nom de 150 caractères accepté et 151 refusé ; description de 3000 acceptée et
3001 refusée ; nom composé d'espaces refusé ; owner et status envoyés dans le
POST et le PATCH ignorés ; modification du seul name : statut inchangé ;
requête sans jeton : 401 ; deadline de demain acceptée.
Ne modifie PAS le code de l'application. Si un test échoue, signale-le au
lieu de corriger. Ne modifie aucun autre fichier.
```

### Résultats après correction
- `test_projects_crud.py` : **10 tests OK**, dont
  `test_description_change_resets_status_to_draft`.
- Suite `projects` : **82 tests OK** (71 avant) ; suite complète : **248 tests
  OK** (état du 13/10/2026, première série).
- Sortie suivante du 13/10/2026 : suite `projects` à **127 tests OK**, soit
  45 tests de plus. La répartition par fichier n'est pas relevée ici.
- Trous du point 3 : **À COMPLÉTER**. L'écart de 82 à 127 tests laisse penser
  que des tests ont été ajoutés, mais rien ne dit lesquels. À relever avec
  `git --no-pager grep -n "def test_" projects/tests/test_projects_crud.py`
  (le fichier comptait 10 tests).

### Limite connue
- Cause de la 400 non documentée.
- Trous de tests du point 3 : état à relever (voir ci-dessus) ; cassures
  volontaires à faire (filtre `owner`, `status` en lecture seule, `>` contre
  `>=` pour la deadline, contrôle du rôle).
- Permission `IsApprovedUser` : un seul usage, sur la liste publique ; les vues
  du porteur utilisent `IsProjectOwner`, dont le contenu reste à lire.
- Retour à DRAFT déclenché par la présence du champ et non par un changement
  de valeur (point 6) : défaut confirmé, non corrigé.
- Pas de pagination vérifiée sur `GET /api/projects/`.
- Fusion avec la branche `users` non faite : conflits possibles dans
  `settings.py` et `urls.py`.

### Enseignements
- Un résumé de Copilot ne remplace pas l'exécution de la suite : l'échec n'est
  apparu qu'au lancement des tests.
- Un test qui échoue en 400 ne dit pas si le défaut est dans le test ou dans
  le code : il faut lire le corps de la réponse avant de corriger.
- Une hypothèse (date fixe) doit être vérifiée dans le code avant d'être
  écrite : ici le grep l'a écartée.
- Les numéros de ligne relevés par `grep` se périment dès que le fichier
  évolue : les noter avec leur date.

---

## Entrée 3 : client LLM et exceptions propres à `projects`

### Contexte
Décision : ne pas réutiliser le client de `users` (travail d'une autre
personne). Client Anthropic indépendant, réglages `PROJECT_LLM_PROVIDER`,
`PROJECT_LLM_API_KEY`, `PROJECT_LLM_MODEL` pour éviter tout conflit lors d'une
fusion de branches.

### Prompt initial (résumé)
- `projects/ai/exceptions.py` : LLMError, LLMConfigError, LLMTimeoutError,
  LLMQuotaError, LLMAuthError, LLMServiceError, LLMResponseError.
- `projects/ai/client.py` : `call_llm(system_prompt, user_text)`, timeout en
  constante, un réessai sur timeout ou 5xx, clé dans l'en-tête `x-api-key`.
- Nom du modèle = réglage, jamais une constante.
- Aucun message d'erreur ni log ne contient la clé, l'URL, le texte du projet
  ou le corps de la réponse.
- Tests avec `requests.post` mocké.

### Résultat généré
- `projects/ai/exceptions.py` (751 octets), `projects/ai/client.py`
  (4471 octets) et `projects/tests/test_llm_client.py` (9 tests).

### Tests appliqués
```text
python manage.py test projects.tests.test_llm_client --verbosity 2
git --no-pager grep -n "users" projects/
git --no-pager grep -n -i "x-api-key\|api_key" projects/
git --no-pager grep -n "sk-ant"
git --no-pager grep -n "claude-" projects/ config/
git --no-pager grep -n "PROJECT_LLM" .
git --no-pager grep -n "retry\|attempt\|for \|range(" projects/ai/client.py
git --no-pager grep -n "call_count\|assert_not_called\|assertNotIn" projects/tests/test_llm_client.py
```

### Résultats des tests
- **9 tests, tous OK** : succès, timeout réessayé une fois, 429, 401 et 403,
  5xx réessayé une fois, clé absente sans appel réseau, mode mock sans appel
  réseau, `content` nul, aucune fuite de la clé, du texte du projet ni de
  l'URL dans les messages et logs.
- `git grep "sk-ant"` : aucune clé dans le code (une occurrence, dans ce
  journal).
- `git grep "claude-" projects/ config/` : aucun nom de modèle dans
  `projects/` ; seule occurrence, `LLM_MODEL` du module `users`
  (`settings.py`, ligne 163).
- `git grep "PROJECT_LLM"` : réglages dans `settings.py` avec valeurs vides
  par défaut, `.env.example` avec une clé vide.
- `git grep "users" projects/` : aucun import de `users.ai` ; mentions
  restantes : clé étrangère vers `User`, `IsApprovedUser`, migration, un test.
- Les logs du client (« Nouvelle tentative après une erreur temporaire du
  LLM ») diffèrent de ceux de `users` (« Erreur 500 du LLM (essai 1/2) ») :
  les deux clients sont séparés.

### Relecture : problèmes constatés
1. **Contrôles confirmés par le grep** : le nombre d'essais est une constante
   (`MAX_ATTEMPTS`, boucle ligne 55) ; `call_count == 2` est vérifié pour le
   timeout (ligne 69) et pour le 5xx (ligne 101) ; `assert_not_called` est
   vérifié pour la clé absente (ligne 113) et le mode mock (ligne 137) ; le
   test de fuite contrôle la clé, le texte du projet et l'URL (lignes 164 à
   166).
2. **Trou probable** : `test_quota_error` annonce « sans réessai » dans sa
   docstring, mais aucun `call_count` n'est vérifié pour le 429, ni pour les
   401 et 403 (seules les lignes 69 et 101 en contiennent). Un réessai sur
   ces codes passerait donc les tests. À confirmer par cassure volontaire.
3. `PROJECT_LLM_MODEL` est vide par défaut : sans valeur dans `.env`, le
   client lève `LLMConfigError`. Voulu, mais à renseigner avant l'essai réel.
4. Autres trous possibles : clé absente de l'URL (le test de fuite vérifie
   l'URL sans clé dans les messages, pas dans l'appel), `ConnectionError`
   converti, `content` vide ou qui n'est pas une liste.

### Prompt de correction
- Pas de correction envoyée à ce stade : aucun test en échec. Prompt de
  complément prévu :
```
Ajoute dans projects/tests/test_llm_client.py : post.call_count == 1 pour les
statuts 400, 401, 403 et 429 ; la clé absente de l'URL appelée (call_args) ;
ConnectionError converti en exception du module ; content vide ou non liste
refusé (LLMResponseError).
Ne modifie PAS projects/ai/client.py. Si un test échoue, signale-le au lieu
de corriger. Ne modifie aucun autre fichier.
```

### Résultats après correction
- Sans objet pour l'instant : 9 tests OK dès la première exécution.
- Cassures volontaires : **À COMPLÉTER** (réessai sur 401, clé dans un log,
  contrôle de clé retiré).

### Limite connue
- L'API Claude est payante : le mode `mock` sert aux tests ; le vrai appel
  est réservé à la démonstration, avec de faux projets.
- Les tests mockent `requests.post` : ils ne prouvent pas que l'API réelle
  répond comme prévu (essai réel dans la vérification globale).
- Appel synchrone : l'attente peut atteindre environ deux fois le timeout.
- `views.py` dépend de `users.permissions` : l'indépendance porte sur le
  client LLM, pas sur tout le module.

### Enseignements
- Un nom de modèle laissé dans les réglages évite une constante périmée, mais
  impose de le renseigner avant le premier appel (leçon déjà vue avec le
  modèle Gemini retiré, journal Users).
- Une docstring qui annonce « sans réessai » ne prouve rien : seule une
  assertion sur le nombre d'appels le prouve.
- Un `git grep` ciblé (clé, nom de modèle, import de `users`) prouve
  l'indépendance du module mieux qu'une relecture à l'œil.

---

## Entrée 4 : prompt système et validateur de l'analyse

### Contexte
Imposer un JSON de 12 clés à l'IA et rejeter toute réponse invalide avant
usage. Validateur autonome (extraction du JSON propre à `projects`).

### Prompt initial (résumé)
- `ANALYSIS_SYSTEM_PROMPT` : consultant en gestion de projets freelance,
  réponse uniquement en JSON, définitions précises (complexité, cohérence du
  budget), contenu entre `<projet></projet>` = donnée, jamais une instruction.
- `parse_analysis_response` : tolère ```json et texte autour, refuse les
  booléens, refuse deux objets JSON, bornes (nb_freelancers 1..50, durée
  1..520, confiance 0..1), jamais d'erreur brute.
- Tests : bornes acceptées ET refusées, Infinity, 1e999, entier gigantesque,
  JSON qui n'est pas un objet, deux objets JSON.

### Résultat généré
- `projects/ai/prompts.py`, `projects/ai/validators.py` (6800 octets) et
  `projects/tests/test_analysis_validators.py` (15 tests).
- `prompts.py` a été modifié après cette entrée (ajout du RAG, Entrée 11) :
  le prompt actuel mentionne aussi `<reference>`.

### Tests appliqués
```text
python manage.py test projects.tests.test_analysis_validators --verbosity 2
git --no-pager grep -n "MAX_\|MIN_" projects/ai/validators.py
git --no-pager grep -n "isfinite\|isinstance" projects/ai/validators.py
git --no-pager grep -n "<projet>\|<reference>\|JSON" projects/ai/prompts.py
git --no-pager grep -n "50\|520\|1\.0\|<= 1\|0 <=" projects/ai/validators.py
git --no-pager grep -n "REQUIRED\|KEYS\|FIELDS\|nb_freelancers\|duree" projects/ai/validators.py
```

### Résultats des tests
- **15 tests, tous OK** : booléen refusé, bornes acceptées, hors bornes
  refusées, budget minimum supérieur au maximum refusé, éléments vides,
  entier gigantesque sans erreur brute, entrée non modifiée, clôture ```json
  et texte autour tolérés, JSON invalide, racine non objet, Infinity et
  exposants infinis, énumérations normalisées, espaces retirés, deux objets
  JSON refusés, exactement les douze champs renvoyés.
- Booléens rejetés avant le test numérique (lignes 134 et 148) ; une liste de
  plus de `MAX_ITEMS` éléments est **rejetée** (ligne 181), pas coupée.
- `prompts.py` : balises `<projet>` et `<reference>` et réponse JSON seule
  présentes.

### Relecture : problèmes constatés
1. **Nombres magiques confirmés** : seuls `MAX_ITEMS = 50` et
   `MAX_ITEM_CHARS = 500` sont des constantes. Les bornes sont écrites en dur
   aux lignes 103 (`nb_freelancers` 1..50), 105 (`duree_semaines` 1..520) et
   187 (`nb` d'une spécialité 1..50). Le 50 apparaît trois fois avec des
   sens différents. Écart avec la règle « pas de nombres magiques ».
   **Corrigé** (grep du 13/10/2026) : les bornes sont des constantes nommées,
   lignes 10 à 29 de `validators.py` : `MIN_TEAM_SIZE = 1` et `MAX_TEAM_SIZE =
   50` (utilisés pour `nb_freelancers`, ligne 108, et pour le `nb` d'une
   spécialité, ligne 204), `MAX_LIST_ITEMS = 50` (taille des listes),
   `MAX_DURATION_WEEKS = 520` avec `MIN_DURATION_WEEKS` (lignes 113, 116, 119,
   240 et 257), ainsi que `MIN_PHASES`/`MAX_PHASES`, `MIN_MILESTONES`/
   `MAX_MILESTONES`, `MIN_RISKS`/`MAX_RISKS`, `MIN_PERCENTAGE`/
   `MAX_PERCENTAGE` et `MIN_PROBABILITY`/`MAX_PROBABILITY`. Les trois « 50 »
   sont devenus deux constantes de sens distinct (`MAX_TEAM_SIZE`,
   `MAX_LIST_ITEMS`). Les noms `MIN_FREELANCERS` et `MAX_FREELANCERS` du prompt
   n'existent pas : le code utilise `MIN_TEAM_SIZE` et `MAX_TEAM_SIZE`. Il
   reste des littéraux `0` et `1` comme taille minimale de liste (lignes 129 à
   137 et 194).
2. **Les 12 champs** sont listés dans le tuple `_FIELDS` (ligne 13), mais
   aucun test ne vérifie qu'une clé manquante est refusée : 15 tests verts ne
   prouvent pas que les 12 clés sont toutes exigées.
   **Corrigé** : `test_each_required_field_is_rejected_when_missing` (OK,
   `v.txt` du 13/10/2026). Le schéma a par ailleurs grandi : les lignes 108 à
   137 citent déjà au moins 13 clés de premier niveau (`nb_freelancers`,
   `duree_semaines`, `duree_min_semaines`, `duree_max_semaines`, `confiance`,
   `taux_reussite`, `score_complexite`, `facteurs_*`, `hypotheses`,
   `questions_clarification`, `recommandations`), plus les budgets, les
   spécialités, les risques, les jalons et les phases. L'énoncé « JSON de 12
   clés » du contexte est périmé, et `test_valid_response_returns_exactly_the_twelve_fields`
   garde un nom qui ne reflète plus le schéma (sa docstring parle de clés
   supplémentaires ignorées).
3. **`float(value)` avant `isfinite`** (`_finite_number`) : un entier
   gigantesque lève `OverflowError` à cet endroit. Le test passe, donc une
   interception existe ailleurs. **Relevé le 13/10/2026**
   (`git grep "try:\|except"`) : un `try` ligne 50 avec `except
   LLMResponseError` ligne 54, puis `except (TypeError, ValueError,
   OverflowError, RecursionError)` ligne 56 (filet de la fonction principale),
   et deux interceptions locales du même tuple, lignes 70-72 et 84-86.
   `OverflowError` est donc attrapée à trois endroits ; `RecursionError`
   aussi (JSON très imbriqué), ce que le prompt ne demandait pas. Laquelle
   attrape l'entier gigantesque ? Non lu ; secondaire, car
   `test_huge_integer_is_rejected_without_raw_error` passe (`v.txt`, 26 tests
   OK).
4. Messages d'erreur : un message générique unique (« Réponse d'analyse
   invalide. »), aucun extrait de la réponse : pas de fuite.
5. Autres trous, d'après les noms des tests : énumération inconnue, liste de
   51 éléments, élément de 501 caractères, spécialité sans `nom` ou `nb`.
   **Comblés** (`v.txt`, 26 tests OK) : `test_unknown_complexity_is_rejected`,
   `test_fifty_specialities_are_accepted_but_fifty_one_are_rejected`,
   `test_five_hundred_character_item_is_accepted_but_five_hundred_one_is_rejected`
   et `test_speciality_requires_name_and_count`.
6. Points meilleurs que `users` : deux objets JSON refusés au lieu de
   retenir le premier ; liste trop longue rejetée au lieu d'être coupée.

### Prompt de correction
- Prompt de complément (à envoyer, puis noter ce qui échoue) :
```
Ajoute dans projects/tests/test_analysis_validators.py les tests suivants :
- une réponse sans l'une des 12 clés est rejetée (une vérification par clé, avec subTest) ;
- complexité inconnue rejetée ;
- liste de 50 éléments acceptée et de 51 rejetée ;
- élément de 500 caractères accepté et de 501 rejeté ;
- spécialité sans "nom" ou sans "nb" rejetée ;
- le message de LLMResponseError ne contient aucun extrait de la réponse brute.
Ne modifie PAS projects/ai/validators.py. Si un test échoue, signale-le au lieu de corriger.
Ne modifie aucun autre fichier.
```
- Prompt pour les nombres magiques (séparé, un seul sujet) :
  « Remplace les bornes 1, 50 et 520 par des constantes nommées
  (`MIN_FREELANCERS`, `MAX_FREELANCERS`, `MAX_DURATION_WEEKS`, etc.) sans
  changer le comportement ; les 15 tests existants doivent rester verts. »

### Résultats après correction
- `test_analysis_validators.py` : **26 tests, tous OK** (`v.txt`, 13/10/2026),
  contre 15 à l'origine. Les six sujets du prompt de complément y figurent
  (clé manquante avec `subTest`, complexité inconnue, 50/51 spécialités,
  500/501 caractères, spécialité sans `nom` ou `nb`, message sans extrait de la
  réponse brute), avec des tests ajoutés pour les phases, les budgets et les
  bornes détaillées (`test_phase_count_and_percentage_sum_are_coherent`,
  `test_phase_durations_specialities_and_team_sum_are_coherent`,
  `test_budget_recommended_must_be_between_bounds`,
  `test_detailed_bounds_are_accepted_and_refused`,
  `test_structured_booleans_are_rejected`).
- Défaut réel trouvé par ces tests : **À COMPLÉTER** (la sortie finale est
  verte ; dire si un test a échoué à sa première exécution).
- Nombres magiques : corrigés (relecture, point 1).

### Limite connue
- Le validateur vérifie la forme, pas la pertinence de l'analyse (même
  constat que pour le coach du module Users : un JSON valide n'est pas une
  réponse correcte).
- Aucun contrôle de cohérence entre champs (budget et nombre de freelancers),
  à part budget minimum inférieur ou égal au maximum.
- Réponse avec plusieurs objets JSON : refusée, le porteur peut relancer.

### Enseignements
- Avoir retenu les leçons de `users` dans le prompt de départ (booléens,
  nombres spéciaux, deux objets JSON) a évité de refaire les mêmes erreurs :
  les 15 tests passent dès la première génération.
- Les tests verts ne détectent pas les nombres magiques : seul le grep les a
  révélés.
- Les noms des tests montrent ce qui manque : aucun ne parle d'une clé
  absente.

---

## Entrée 4 bis : anonymiseur et nettoyage du texte (`sanitizer.py`)

### Contexte
Le texte du projet est envoyé à un LLM externe : il faut retirer les données
personnelles et neutraliser les balises avant l'appel.

### Prompt initial (résumé)
- Ordre fixe : NFKC, anonymisation (emails, téléphones, liens), troncature
  sans couper un placeholder, remplacement de `<` et `>` par `‹` et `›`.
- Tests négatifs ET positif (un texte normal reste inchangé), email en
  caractères pleine largeur.

### Résultat généré
- `projects/ai/sanitizer.py` (2018 octets) et
  `projects/tests/test_sanitizer.py` (9 tests).

### Tests appliqués
```text
python manage.py test projects.tests.test_sanitizer --verbosity 2
git --no-pager grep -n "def test_" projects/tests/test_sanitizer.py
git --no-pager grep -n "MAX_\|NFKC\|normalize\|def " projects/ai/sanitizer.py
Get-Content projects\ai\sanitizer.py -Encoding UTF8
python manage.py test projects --verbosity 2     (13/10/2026, 127 tests)
```

### Résultats des tests
- **9 tests, tous OK** : e-mail, téléphone, lien, e-mail pleine largeur
  anonymisé après NFKC, troncature sans couper un placeholder, balise de fin
  ASCII neutralisée, balise de fin pleine largeur neutralisée, texte normal
  inchangé, neutralisation limitée aux chevrons.
- Le texte transmis lors des tests de l'Entrée 5 contient `[EMAIL]`, `[TEL]`,
  `[LIEN]` et `‹/projet›` : l'anonymisation et la neutralisation fonctionnent
  de bout en bout.
- **Sortie du 13/10/2026** (`s.txt`, relu) : **10 tests, tous OK**. Les 9 tests
  d'origine sont verts et `test_dates_and_amounts_are_not_anonymized_as_phones`
  (ligne 26, docstring « Les dates et montants restent inchangés ») passe. Le
  texte testé contient `2026-11-12`, `12/11/2026`, `1 500 000`, `10000.00` et
  `15 000 TND`. `test_phone_is_anonymized` couvre `+33 6 12 34 56 78` et
  `06.12.34.56.78` (lecture du fichier, lignes 21 à 24). Les cas du prompt de
  correction sont donc tous présents.

### Relecture : problèmes constatés
1. **Ordre conforme au prompt** : `sanitize_project_text` appelle
   `normalize_text`, `anonymize_text`, `truncate_text`, puis
   `neutralize_text`. La neutralisation vient en dernier (elle ne change pas
   la longueur) et plus aucune regex n'est utilisée pour les balises : la
   leçon de `users` (Entrée 2, étape 6b) a été appliquée dès le prompt.
2. **Soupçon de faux positifs du téléphone.** `_PHONE_PATTERN`
   (`\+?\d[\d\s().-]{7,}\d`) accepte tout groupe de 9 caractères ou plus fait
   de chiffres, espaces, points et tirets. Une date comme `2026-11-12` et un
   montant comme `1 500 000` risquaient d'être remplacés par `[TEL]`, ce qui
   est gênant ici, car un projet contient des budgets et des dates.
   **État au 13/10/2026 : le test « dates et montants inchangés » passe, et le
   motif a changé.** `_PHONE_PATTERN` (lignes 16 à 22) n'est plus le motif
   permissif cité plus haut. Il compte trois formes : un `+` suivi d'un
   indicatif et de 4 à 6 groupes de 1 à 3 chiffres ; un `0` suivi d'un chiffre
   et de 4 groupes de 2 chiffres séparés par une espace ou un point ; ou un `0`
   suivi de 9 chiffres, le tout borné par `(?<!\w)` et `(?!\w)`. C'est la
   correction décrite dans le prompt de correction (préfixe `+` ou `0` initial,
   séparateurs réguliers). Indices que cette correction n'est pas commitée :
   `git log` ne montre qu'un commit (`bec2257`), et `git diff --stat` signale
   `sanitizer.py` modifié (6 lignes) et `test_sanitizer.py` augmenté de 6
   lignes, ce qui correspond au test des dates (lignes 26 à 30). Le motif
   d'origine n'a pas été comparé : **À COMPLÉTER** par `git --no-pager diff --
   projects/ai/sanitizer.py projects/tests/test_sanitizer.py`, et dire si le
   test a échoué à sa première exécution (faux positif confirmé) ou non.
3. **Pas de test de la fonction complète** `sanitize_project_text` (ordre
   des quatre étapes), ni du cas `max_chars < 0` (`ValueError`) :
   **confirmé le 13/10/2026** d'après les noms des 10 tests (`git grep "def
   test_"`). Seuls les morceaux sont testés (e-mail, téléphone, lien,
   troncature, balises), pas leur enchaînement.
4. Anonymisation par regex : les noms propres et adresses postales ne sont
   pas détectés (limite connue).

### Prompt de correction
- Si le point 2 est confirmé (deux temps, un sujet par prompt) :
```
Dans projects/tests/test_sanitizer.py, ajoute d'abord les tests suivants :
"2026-11-12" reste inchangé ; "1 500 000 EUR" reste inchangé ; "10000.00"
reste inchangé ; "+33 6 12 34 56 78" et "06.12.34.56.78" sont remplacés par
[TEL]. Ne modifie PAS sanitizer.py. Si un test échoue, signale-le au lieu de
corriger. Ne modifie aucun autre fichier.
```
  Puis, si des tests échouent : « Corrige `_PHONE_PATTERN` pour exiger un
  préfixe `+` ou un `0` initial et des séparateurs réguliers, sans casser les
  9 tests existants ni les nouveaux. Ne modifie aucun autre fichier. »
- Prompt réellement envoyé : **À COMPLÉTER** (les valeurs testées sont connues, voir « Résultats des tests »).

### Résultats après correction
- `test_sanitizer.py` : **10 tests OK** (13/10/2026), dont le nouveau
  `test_dates_and_amounts_are_not_anonymized_as_phones`.
- Suite `projects` : **127 tests OK**.
- Valeurs testées : voir « Résultats des tests ». Cas non couverts : voir
  « Limite connue ».

### Limite connue
- Une regex d'anonymisation ne détecte pas toutes les données personnelles.
- Le motif exige un `+` ou un `0` initial et des groupes réguliers : d'après
  sa lecture, un numéro tunisien écrit `+216 20 123 456` (indicatif puis 3
  groupes seulement) ou `20 123 456` n'est pas reconnu, alors que
  `+216 20 12 34 56` l'est (4 groupes). Les montants du test sont en TND : ce
  format local est pertinent. **À tester** (`anonymize_text("Appelez le +216
  20 123 456")`) ; non testé à ce jour.

### Enseignements
- Fixer l'ordre des opérations dans le prompt a évité l'erreur de `users` :
  les 9 tests passent dès la première génération.
- Des tests « un texte normal reste inchangé » ne couvrent que le texte
  choisi : un texte réaliste (dates, montants) peut révéler un faux positif.
- Un soupçon de défaut tiré de la lecture d'une regex se tranche par un test :
  le test dates et montants existe maintenant et passe.
- Une sortie de test coupée en haut de l'écran perd des tests : rediriger vers
  un fichier (`... 2>&1 | Out-File sortie.txt`) pour tout garder.
- Un motif plus strict supprime les faux positifs mais peut laisser passer des
  formats locaux : les tests doivent couvrir les formats réellement attendus
  (ici les numéros tunisiens, absents des cas testés).

---

## Entrée 5 : service d'analyse, endpoint et mode simulé

### Contexte
Service qui envoie le projet nettoyé au LLM, valide la réponse, l'enregistre
et passe le projet en ANALYZED.

### Prompt initial (résumé)
- Modèle `ProjectAnalysis`, service `analyze_project`,
  `POST /api/projects/<id>/analyze/`.
- Succès : statut ANALYZED. Erreur LLM : réponse 200 avec `error`, statut
  inchangé, aucun contenu du projet ni clé dans les messages.
- Mode `mock` : simulateur à règles, `simulated: true`.
- Throttle DRF.

### Résultat généré
- Modèle `ProjectAnalysis` (migration `0002`), `projects/services/analysis.py`,
  `projects/ai/simulator.py`, endpoint d'analyse, `ProjectAnalysisThrottle`
  (taux dans `PROJECT_ANALYSIS_THROTTLE_RATE`), tests dans
  `projects/tests/test_analysis_service.py`.

### Tests appliqués
```text
python manage.py test projects.tests.test_analysis_service --verbosity 2
python manage.py test projects
python manage.py test
git --no-pager grep -n "simulated" projects/
git --no-pager grep -n -i "throttle" config/settings.py projects/
git --no-pager grep -n "10/hour" projects/ config/     (13/10/2026)
```

### Résultats des tests (avant correction)
- Suite `projects` : 71 tests, 4 échecs, dont 3 dans ce fichier :
  - `test_invalid_llm_response_keeps_status_and_records_error` : 502 au lieu
    de 200 ;
  - `test_missing_api_key_is_not_exposed` : 502 au lieu de 200 ;
  - `test_text_is_anonymized_and_tags_are_neutralized` : `</projet>` trouvé
    dans le texte transmis.
- Le 4e échec est celui du CRUD (Entrée 2).

### Relecture : problèmes constatés
1. **Spécification, code et tests en désaccord** : le prompt demandait 200
   avec `error` en cas d'erreur du LLM, le code renvoyait 502. Seule
   l'exécution des tests l'a révélé. Règle retenue : toute erreur LLM donne
   200 avec `error` générique, statut du projet inchangé.
2. **Test de neutralisation trop strict** : il cherchait `</projet>` dans
   tout le texte, alors que le service ajoute lui-même cette balise puis
   `<reference>` (RAG, Entrée 11). Le contenu du projet était bien neutralisé
   (`‹/projet›`) : le défaut était dans le test, pas dans le code.
3. **Valeur de secours `"10/hour"` en dur : CONFIRMÉE le 13/10/2026.**
   `git grep "10/hour" projects/ config/` renvoie deux lignes :
   - `config/settings.py:180` : `"10/hour",` ; par symétrie avec les lignes
     182 à 184 (`PROJECT_CHATBOT_THROTTLE_RATE = os.getenv(…, "30/hour")`), c'est
     la valeur par défaut de `os.getenv` pour `PROJECT_ANALYSIS_THROTTLE_RATE`
     (les lignes 178 et 179 n'ont pas été lues) ;
   - `projects/views.py:51` : `getattr(settings,
     "PROJECT_ANALYSIS_THROTTLE_RATE", "10/hour")` : le même taux est
     recopié comme valeur de secours dans la vue. C'est la duplication à
     supprimer : si le réglage change, la vue garde l'ancien taux en cas
     d'absence. L'assistant fait mieux : `ProjectChatbotThrottle.get_rate`
     (`views.py:70`) appelle `getattr(settings, "PROJECT_CHATBOT_THROTTLE_RATE")`
     sans valeur de secours. Le correctif attendu pour l'analyse suit ce
     modèle.
4. Projet publié refusé en **400** à l'analyse, alors que publier ou refuser
   un mauvais état donne **409** : incohérence à trancher.
   **Confirmé le 13/10/2026** (`git grep "HTTP_400\|HTTP_409"` et liste des
   classes) : `ProjectAnalyzeView` (ligne 124) refuse un projet PUBLISHED ou
   DECLINED (test ligne 143) avec **400** (ligne 153), alors que
   `ProjectDecisionView` (ligne 227) répond **409** aux lignes 242 et 247
   (test `status != ANALYZED` ligne 239). L'incohérence est toujours là.
   Règle à choisir : un état incompatible avec l'action est un conflit, donc
   409 partout ; les 400 restent réservés aux données invalides (comme aux
   lignes 171 et 176 de l'assistant).
   Le test `test_published_project_returns_400` (`test_analysis_service.py`,
   ligne 137) fige le 400 actuel : passer à 409 impose de modifier aussi ce
   test.
5. `simulated` n'est testé qu'en positif (`assertTrue`) : un
   `simulated = True` en dur passerait les tests.
   **Corrigé** (13/10/2026) : `test_anthropic_provider_is_not_simulated`
   (`test_analysis_service.py`, ligne 86) vérifie `assertFalse(
   response.data["simulated"])` (ligne 92) avec `call_llm` mocké ; les cas
   positifs sont aux lignes 224, 233 et 310. Côté code, `analysis.py` ligne 40
   calcule `simulated = getattr(settings, "PROJECT_LLM_PROVIDER", "") ==
   "mock"` : la valeur dépend du réglage, elle n'est pas écrite en dur.

### Prompt de correction
```
CONTEXTE : projet Django/DRF décrit dans .github/copilot-instructions.md.
Trois tests de projects/tests/test_analysis_service.py échouent :
- test_invalid_llm_response_keeps_status_and_records_error : 502 au lieu de 200
- test_missing_api_key_is_not_exposed : 502 au lieu de 200
- test_text_is_anonymized_and_tags_are_neutralized : "</projet>" trouvé dans le texte

OBJECTIF : appliquer la règle suivante : toute erreur LLM donne une réponse 200
avec le champ `error` renseigné (message générique), le statut du projet inchangé.

CONTRAINTES :
- Corrige le code (views.py ou analysis.py) pour les deux premiers tests.
- Pour le troisième : le test est trop strict. Extraire le contenu du projet
  (entre <projet> et la dernière </projet>), vérifier qu'il ne contient aucune
  balise, et vérifier que </projet> apparaît exactement une fois dans le texte complet.
- Explique pour chaque test si tu as modifié le code ou le test, et pourquoi.
- Ne modifie aucun autre fichier.
```
- Prompt prévu pour le point 3 (un seul sujet, **non encore envoyé**) :
```
CONTEXTE : projet Django/DRF décrit dans .github/copilot-instructions.md.
La valeur "10/hour" est écrite dans projects/views.py (ligne 51, valeur de
secours de getattr) et dans config/settings.py (ligne 180).

OBJECTIF : supprimer la valeur de secours en dur dans views.py.

CONTRAINTES :
- La cadence est lue uniquement depuis settings.PROJECT_ANALYSIS_THROTTLE_RATE.
  Si config/settings.py ne définit pas déjà ce réglage, l'y définir une seule
  fois.
- Aucun changement de comportement : le test de throttle (429) de
  projects/tests/test_analysis_service.py doit rester vert.
- Ne modifie aucun autre fichier. Si un test échoue, signale-le.
```
  Contrôle après correction : `git --no-pager grep -n "10/hour" projects/
  config/` ne doit plus renvoyer que `config/settings.py`.

### Résultats après correction
- `test_analysis_service.py` : **9 tests OK** (succès, erreur LLM historisée,
  clé absente sans fuite, autre porteur en 404, projet publié refusé,
  anonymisation et neutralisation, simulateur sur deux cas, throttle 429).
- Relevé du 13/10/2026 (`git grep "def test_"`) : le fichier compte maintenant
  **18 tests** (9 à l'origine), dont `test_structured_project_values_are_complete_in_llm_text`,
  `test_error_does_not_contain_project_text` et cinq tests du simulateur
  (`test_mock_...`).
- Le code applique la règle : `analysis.py` renvoie une réponse avec
  `error` générique (`GENERIC_LLM_ERROR`, ou `INTERNAL_ERROR` pour une erreur
  inattendue) et enregistre l'échec sans le texte du projet.
- Suite `projects` : **82 tests OK** ; suite complète : **248 tests OK**
  (première série du 13/10/2026) ; puis **127 tests OK** dans `projects`
  (sortie suivante).
- Point 3 (`"10/hour"`) : **non corrigé** au 13/10/2026 (grep ci-dessus).

### Limite connue
- Analyse synchrone : durée jusqu'à environ 40 s (deux essais).
- Le mode `mock` produit une analyse à règles : il ne prouve pas la qualité
  d'un vrai modèle (essai réel dans la vérification globale).
- Point 3 de la relecture (`"10/hour"`) : toujours présent dans `views.py`
  ligne 51 au 13/10/2026. Point 4 (400 contre 409) : toujours présent
  (lignes 153, 242 et 247), figé par un test. Point 5 (`simulated`) : corrigé.
- Throttle de l'assistant : pas de valeur de secours en dur (`views.py:70`),
  défaut `30/hour` défini une seule fois dans `settings.py` (lignes 182 à
  184). La crainte notée plus haut est écartée.
- Tests demandés plus haut : présents (`git grep "def test_"`, 18 tests) : 401
  sans jeton (`test_missing_token_returns_401`, ligne 115), 403 freelance
  (`test_freelancer_returns_403`, ligne 123), erreur LLM après une analyse
  réussie (`test_llm_error_after_success_preserves_status_and_previous_analysis`,
  ligne 191) et `simulated` faux avec un vrai fournisseur (ligne 86).

### Enseignements
- Quand le prompt contient une règle et que le code en applique une autre,
  seuls les tests exécutés montrent l'écart : il faut décider de la règle
  avant de corriger, sinon on aligne les tests sur le mauvais comportement.
- Un test peut devenir faux quand le code évolue (ajout du RAG) : un échec
  n'est pas toujours un défaut du code.
- Un test qui n'existe qu'en positif (`simulated` vrai) ne détecte pas une
  valeur codée en dur.
- Un défaut relevé à la relecture reste dans le code tant qu'aucun prompt de
  correction n'est envoyé : le grep de contrôle le prouve (ici `"10/hour"`).

---

## Entrée 6 : décision du porteur et liste publique

### Contexte
Le porteur publie ou refuse le projet après l'analyse ; les projets publiés
sont visibles dans une liste publique qui ne doit rien divulguer de sensible.

### Prompt initial (résumé)
- `POST /publish/` et `/decline/` : seulement si ANALYZED (sinon 409),
  publication exigeant une analyse réussie.
- `GET /api/projects/published/` : liste paginée, serializer à liste blanche,
  jamais d'email, de risques ni d'information du propriétaire.
- Filtre `?status=` (valeur inconnue : 400).

### Résultat généré
- Vues de décision et de liste publique ; tests dans
  `projects/tests/test_decision_and_public.py`.

### Tests appliqués
```text
python manage.py test projects.tests.test_decision_and_public --verbosity 2
python manage.py check
python manage.py makemigrations --check --dry-run
```

### Résultats des tests
- Tests dédiés : **11 réussis**.
- Relance `--verbosity 2` du 13/10/2026 : « Found 11 test(s) … Ran 11 tests …
  OK ». Couverts : refus d'un projet analysé, projets DRAFT/ANALYZED/DECLINED
  masqués, autre porteur en 404, filtre `status` valide et inconnu, JSON public
  sans propriétaire ni analyse privée, projet publié visible, champs métier
  verrouillés après publication, publication d'un projet analysé, brouillon en
  409, analyse en erreur en 409.
- `check` : OK. Vérification des migrations : OK.

### Relecture : problèmes constatés
1. Relecture avec la checklist de la séance 3 (lecture de `views.py`, lignes
   227 à 275, et de `serializers.py`, 13/10/2026) :
   - **Décision** : `ProjectDecisionView` cherche le projet avec
     `owner=request.user` (404 sinon), refuse un projet qui n'est pas ANALYZED
     (**409**), puis un projet sans analyse portant un résultat
     (`result__isnull=False`, **409** « Une analyse réussie est requise. ») :
     conforme au prompt.
   - **Liste publique** : `PublishedProjectListView` filtre sur
     `status=PUBLISHED` avec `prefetch_related("analyses")` (pas de requête N+1),
     pagination par `PAGE_SIZE`, permission `IsApprovedUser`, serializer
     `PublicProjectSerializer`.
   - **Liste blanche : conforme.** `PublicProjectSerializer` expose `id`,
     `name`, `description`, `deadline`, `estimated_amount` et `analysis` ;
     `PublicAnalysisSerializer` expose `budget_min`, `budget_max`,
     `nb_freelancers`, `specialites`, `duree_semaines` et `complexite`. Ni
     `owner`, ni e-mail, ni risques. `get_analysis` ne retient qu'une analyse
     avec résultat et sans erreur. Le test
     `test_public_json_has_no_owner_or_private_analysis_fields` le vérifie.
   - **Filtre `?status=`** : il est dans `ProjectListCreateView` (liste du
     **porteur**, lignes 82 à 87, 400 par `ValidationError`) et testé par
     `test_owner_status_filter_accepts_valid_value` et
     `test_owner_status_filter_rejects_unknown_value`. Le résumé du prompt le
     plaçait sous `/published/` : l'écart venait de la rédaction du journal,
     pas du code.
2. **Points à corriger ou à vérifier :**
   - `decision` : le code écrit `PUBLISHED if decision == "publish" else
     DECLINED` ; toute autre valeur d'URL deviendrait un refus. **À
     COMPLÉTER** : lire `projects/urls.py` pour voir si le chemin n'accepte que
     `publish` et `decline`.
   - `from django.http import Http404` est importé **dans** la méthode `post`
     (style : import en tête de fichier, ou `get_object_or_404`).
   - Description publiée en clair : le serializer public renvoie `description`
     telle que saisie, sans anonymiseur (le porteur décide de publier, mais un
     e-mail écrit dans la description serait visible).
   - Aucun des 11 tests ne porte sur l'accès à la liste publique sans jeton
     (401) ni avec un compte non accepté (`IsApprovedUser`), ni sur la
     pagination (d'après les noms).

### Prompt de correction
- Aucun prompt envoyé : aucun test en échec. Prompt prévu pour le point 2 de la
  relecture, à envoyer **après** lecture de `projects/urls.py` :
```
CONTEXTE : projet Django/DRF décrit dans .github/copilot-instructions.md.
Vue #file:projects/views.py (ProjectDecisionView) et #file:projects/urls.py.

OBJECTIF : sécuriser la décision de publication.

CONTRAINTES :
- Toute valeur de `decision` autre que "publish" ou "decline" est refusée
  (404 ou 400), jamais traitée comme un refus.
- Remonter l'import de Http404 en tête de fichier (ou get_object_or_404).
- Aucun changement de comportement pour les cas déjà testés.

FORMAT : un test pour une décision inconnue ; un test 401 sans jeton sur la
liste publique ; un test pour un compte non accepté sur la liste publique.
Ne modifie aucun autre fichier. Si un test échoue, signale-le.
```

### Résultats après correction
- Sans objet : aucune correction envoyée ; les 11 tests restent OK
  (13/10/2026).

### Limite connue
- Description publiée sans anonymisation.
- Pas de test 401 ni « compte non accepté » sur la liste publique, ni de test de
  pagination.
- Décision inconnue : comportement non vérifié (`urls.py` non lu).

### Enseignements
- Le résumé d'un prompt peut mal placer une règle (ici le filtre `?status=`) :
  relire le code et les noms de tests avant de conclure à un défaut.
- Une liste blanche explicite (tuple `fields`) plus un test sur le JSON publié
  protègent mieux qu'une relecture à l'œil.

---

## Entrée 7 : vérification de l'environnement avant le front

### Incidents constatés
1. **Base locale non migrée** : `runserver` a signalé 28 migrations non
   appliquées, alors que les tests passaient (ils utilisent une base
   temporaire). Correction : `python manage.py migrate`.
2. **Aucun utilisateur en base** : Django ne crée aucun compte par défaut.
   Correction : `createsuperuser`, puis création de trois comptes de test
   (ADMIN, PROJECT_OWNER, FREELANCER) avec `moderation_status = OK`.
3. **Commande `curl` mal adaptée à PowerShell** : les guillemets échappés
   étaient supprimés, le serveur a reçu un JSON invalide. Le back répondait
   correctement (erreur JSON explicite, puis « Token non valide »).
   Correction : fichier JSON ou `Invoke-RestMethod`.
4. **Front introuvable** : `npm install` a échoué (`package.json` absent) car
   le projet se trouvait dans un sous-dossier. **Relevé le 13/10/2026** : à la
   racine du dépôt, `Get-ChildItem -Directory` ne liste que `.github`,
   `.venv`, `config`, `docs`, `experiments`, `projects` et `users`, et la
   recherche récursive de `package.json` (profondeur 3, hors `node_modules`)
   ne renvoie **rien** : le front n'est pas dans ce dépôt. Emplacement réel
   (autre dossier ou autre dépôt) : **À COMPLÉTER** (donner le chemin, par
   exemple avec `Get-ChildItem D:\prorojet_IA -Directory`).
5. **Pager de Git** : les `git grep` longs ouvrent un pager (`less`) ; sortie
   avec `q`, ou `git --no-pager` pour éviter le blocage.
6. **`coverage` introuvable** (13/10/2026) : `coverage run --branch manage.py
   test projects` et `coverage report` ont répondu « Le terme coverage n'est
   pas reconnu » : l'outil n'est pas installé dans l'environnement actif (ou
   absent du PATH). Aucune mesure de couverture n'a donc eu lieu. Correction à
   appliquer : `pip install coverage`, puis la forme `python -m coverage ...`
   (voir Vérification globale).
7. **Sortie redirigée mal encodée** (13/10/2026) : `... 2>&1 | Out-File
   -Encoding utf8 v.txt` donne un fichier où « é » devient « Ú » (mauvais
   décodage de la page de code de la console) et où PowerShell ajoute une fausse
   erreur `NativeCommandError` en tête, parce que les lignes de test sont
   écrites sur `stderr`. Les résultats restent justes. Pour un fichier propre
   (à essayer) : `$env:PYTHONUTF8 = "1"` avant la commande, ou `cmd /c "python
   manage.py test projects > sortie.txt 2>&1"`.

### Enseignements
- Des tests verts ne disent rien d'une base locale non migrée ni d'une base
  vide : un essai de bout en bout révèle ce que les tests cachent (même
  constat que l'Entrée 4 du journal Users : `no such column`).
- Une commande proposée par une IA peut être correcte en théorie et fausse
  dans l'environnement réel (ici PowerShell) : l'exécuter et lire l'erreur.
- Un outil de mesure doit être installé avant d'être cité comme résultat :
  une commande écrite dans le journal n'est pas une mesure faite.

---

## Entrées 8 à 10 : front (React, TypeScript, Vite)

À remplir avec le même modèle (prompt initial, résultat, tests manuels,
corrections) :
- **Entrée 8** : types TypeScript et fonctions d'appel à l'API (`projects.ts`,
  `project.ts`).
- **Entrée 9** : page « Nouveau projet » (formulaire, analyse, publier ou non).
- **Entrée 10** : pages « Mes projets » et « Projets publiés ».

Tests manuels à noter (aucun test frontend automatisé) : créer, analyser en
mode `mock`, publier, refuser, supprimer, erreur 429, compte freelance, liste
vide.

Points de vigilance à rappeler dans les prompts front (acquis du module
Users) : afficher la réponse de l'IA en **texte simple** (jamais en HTML),
gérer une réponse 204 sans corps, afficher un bandeau « Analyse simulée »
quand `simulated` est vrai, désactiver le bouton et afficher un indicateur
pendant l'analyse (jusqu'à 40 s).

---

## Entrée 11 : RAG léger (technique de la séance 4)

### Contexte
Adapter l'analyse avec un référentiel local plutôt qu'un réentraînement
(slide 48 : RAG). Pourquoi le RAG plutôt que le fine-tuning : il ne
nécessite aucun réentraînement, reste à jour en modifiant le référentiel et
fonctionne avec des données propres au projet (slide 31).

### Prompt initial (résumé)
- RAG léger : recherche TF-IDF locale dans un référentiel de métiers, section
  `<reference>` ajoutée au prompt, champ `references_used` dans la réponse.

### Résultat généré
- `projects/ai/retrieval.py` (3620 octets), `projects/ai/reference_data.json`
  (2959 octets), modification de `prompts.py`, tests dans
  `projects/tests/test_retrieval.py` (5488 octets).

### Tests appliqués / résultats / relecture / corrections
- **À COMPLÉTER** : `python manage.py test projects.tests.test_retrieval
  --verbosity 2`, relecture de `retrieval.py`, essai avec et sans référence.
- Effet de bord déjà constaté : l'ajout de `<reference>` a rendu trop strict
  le test de neutralisation de l'Entrée 5.

### Limite connue
- Un TF-IDF local est une recherche par mots, pas par sens : contrairement aux
  embeddings (slide 28), il rate les synonymes.
- Le journal Users (Entrée 7) a montré qu'un petit modèle exploite mal le
  contexte fourni : à garder en tête pour juger l'effet du RAG.
- **À COMPLÉTER**.

### Enseignements
- **À COMPLÉTER**.

---

## Entrée 12 : comparaison de deux modèles Claude

- Script : `experiments/compare_models.py` (lit `PROJECT_LLM_API_KEY`, refuse
  de s'exécuter sans clé).
- **À COMPLÉTER** : modèles comparés, 5 faux projets, mesures, décision.
- Rappel de méthode (journal Users, Entrée 5) : comparer taille, vitesse et
  qualité ensemble, dans les mêmes conditions, pour toutes les versions.

---

## Entrée 13 (optionnelle) : audit des tests

- **À COMPLÉTER** : cassures volontaires, tests qui ont échoué, trous comblés.

---

## Entrée 14 : assistant projet (chat avec RAG sur la FAQ et les analyses)

### Contexte
Page « Assistant » du front (menu : Accueil, Mon profil, Gestion de projet,
Assistant). L'utilisateur pose une question (limite de 1000 caractères,
compteur affiché, bouton « Envoyer » désactivé quand le champ est vide) et un
modèle répond à partir d'un contexte récupéré par RAG : FAQ de l'application
et analyses de projets. Le sous-titre de la page annonce : « Posez une
question sur vos projets et les ressources disponibles. »

Consigne anti-hallucination visible dans les réponses : l'assistant ne répond
qu'à partir du contexte fourni et dit quand l'information n'y figure pas
(slide 30 : « Si l'information n'y figure pas, dis-le »).

### Prompt initial
- **À COMPLÉTER** : prompt envoyé à Copilot pour la route, le service et la
  page (non fourni dans les documents de travail).
- **À COMPLÉTER** : modèle utilisé, source du contexte (FAQ, analyses) et
  nombre de blocs injectés (top-k).

### Résultat généré
- Fichiers (lecture et greps du 13/10/2026), tous côté Django :
  - `projects/views.py` : `ProjectChatbotView` (ligne 159, méthode `post`) avec
    la permission `IsProjectOwner` (seuls les porteurs de projet peuvent
    interroger l'assistant) et `ProjectChatbotThrottle` (ligne 54 ; `get_rate`
    sans valeur de secours, ligne 70) ; constantes `MAX_CHATBOT_QUESTION_CHARS =
    1000` et `MAX_CHATBOT_ANSWER_CHARS = 4000` ;
  - `projects/ai/client.py` : `call_chatbot_llm` (fournisseur lu ligne 109,
    réponse fixe `CHATBOT_MOCK_RESPONSE` ligne 29 en mode `mock`) ;
  - `projects/ai/prompts.py` : `CHATBOT_SYSTEM_PROMPT` (ligne 67) ;
  - `projects/ai/faq_data.json` (FAQ) et `projects/tests/test_chatbot_retrieval.py`
    (31 lignes) ; les fonctions `load_faq_corpus`, `build_user_analysis_corpus`
    et `retrieve_corpus` sont importées par la vue, leur fichier n'a pas été lu
    (probablement `retrieval.py`, modifié d'après `git diff --stat`) ;
  - `config/settings.py` : `CHATBOT_LLM_PROVIDER` (ligne 172, défaut `mock`) et
    `PROJECT_CHATBOT_THROTTLE_RATE` (lignes 182 à 184, défaut `30/hour`) ;
    `.env.example`, ligne 16 (`CHATBOT_LLM_PROVIDER=mock`).
- Déroulement de `post` : question non vide et d'au plus 1000 caractères (sinon
  400), passage par `sanitize_project_text` (anonymisation et neutralisation des
  chevrons, comme pour l'analyse), corpus = FAQ + analyses **de l'utilisateur
  connecté** (`build_user_analysis_corpus(request.user)`), recherche
  `retrieve_corpus`, contexte = blocs trouvés en JSON, ou `APP_OVERVIEW` si
  aucun bloc, prompt `<contexte>…</contexte><question>…</question>`, appel du
  modèle, réponse vérifiée (chaîne non vide, au plus 4000 caractères). Erreur du
  modèle : 200 avec `answer: null` et `error` générique (même règle que
  l'analyse) ; sinon 200 avec `answer`, `sources` (identifiants des blocs) et
  `simulated`.
- **À COMPLÉTER** : nombre de blocs injectés (top-k), modèle utilisé, composant
  React (le front est hors de ce dépôt) et tests de la vue (401, 403 freelance,
  400, 200, 429) : seul `test_chatbot_retrieval.py` est connu (`git --no-pager
  grep -n "def test_" projects/tests/ | Select-String -Pattern
  "hatbot|ssistant"`).

### Essais manuels (captures du 13/10/2026)

| Question posée | Réponse de l'assistant | Verdict |
|---|---|---|
| « quelle est le dernier projet postulé ? » | Se présente comme l'assistant de Freelancy, répond uniquement sur l'application, la FAQ et les analyses ; indique que l'information sur le dernier projet postulé ne figure pas dans le contexte | Refus propre, aucune invention |
| « bnjour » (faute de frappe) | Salue, rappelle son périmètre (application, FAQ, analyses de projets) et propose son aide | Correct, la faute est comprise |
| « combien il y'a de projet disponibles ? » | « D'après le contexte fourni, cette information n'y figure pas. Je ne peux donc pas vous répondre. » | Refus propre, mais question légitime sans réponse utile |

L'interface fonctionne de bout en bout (front, route, modèle, réponse).

### Relecture : problèmes constatés
1. **Un refus correct n'est pas une réponse utile.** Les deux questions
   (« dernier projet postulé », « combien de projets disponibles ») sont
   légitimes, mais le contexte ne contient pas ces données. Le refus vient du
   contenu du contexte, pas du modèle.
2. **Périmètre annoncé supérieur au périmètre réel.** Le sous-titre promet
   des réponses sur « vos projets », alors que l'assistant ne connaît que la
   FAQ et les analyses. Il ne connaît pas l'état courant de la base.
3. **Confusion possible entre deux types de données.**
   - Connaissance documentaire (FAQ, guides, analyses) : adaptée au RAG.
   - Données transactionnelles (nombre de projets publiés, candidatures de
     l'utilisateur) : la bonne source est une requête ORM, pas une recherche
     sémantique.
4. Cause exacte du refus (recherche vectorielle qui remonte de mauvais blocs,
   limite du slide 31, ou données absentes de la base documentaire) :
   Voir le point 5 pour la cause probable ; la preuve est à relever dans le
   champ `sources` de la réponse.
5. **Cause probable des deux refus (lecture du code).** Le corpus est la FAQ
   plus les analyses de l'utilisateur ; aucun bloc ne contient le nombre de
   projets publiés ni les candidatures. Si `retrieve_corpus` ne renvoie rien,
   le contexte devient `APP_OVERVIEW` (vue d'ensemble de l'application) : le
   modèle n'a alors aucune donnée chiffrée et répond que l'information n'y
   figure pas. Cela confirme le point 3 : les données absentes viennent du
   corpus, pas d'un défaut du modèle. À prouver : le champ `sources` de la
   réponse JSON (onglet Réseau du navigateur) doit être une liste vide pour ces
   deux questions. L'option B peut s'appuyer sur l'existant :
   `build_user_analysis_corpus(request.user)` filtre déjà par utilisateur.
6. **Mode simulé : hypothèse affaiblie.** `settings.py` ligne 172 définit
   `CHATBOT_LLM_PROVIDER` avec le défaut `mock`, `.env.example` ligne 16 aussi,
   et en mode `mock` `client.py` renvoie une seule réponse fixe
   (`CHATBOT_MOCK_RESPONSE`). Or les trois essais du 13/10 ont donné trois
   réponses différentes (présentation, salutation, refus) : une réponse fixe ne
   l'explique pas, donc un vrai modèle était probablement appelé. Non prouvé :
   la valeur de `simulated` des réponses n'a pas été notée.
7. **Réglage dupliqué.** Le repli `"mock"` est écrit trois fois :
   `settings.py:172`, `views.py:194` (calcul de `simulated`) et `client.py:109`
   (choix du fournisseur). La vue et le client décident séparément : si l'un
   change, `simulated` peut devenir faux. Détail de style : pas d'espace après
   la virgule ligne 194.
8. **Deux familles de réglages.** L'assistant lit `CHATBOT_LLM_PROVIDER` alors
   que l'analyse lit `PROJECT_LLM_*` (Entrée 3). **À COMPLÉTER** : lire
   `client.py` autour de la ligne 109 pour savoir quelle clé et quel modèle
   `call_chatbot_llm` utilise.
9. **Injection de second ordre : à vérifier.** La question est nettoyée
   (`sanitize_project_text`), mais les blocs sont insérés par `json.dumps` sans
   neutralisation visible des chevrons. Les analyses de l'utilisateur sont des
   textes produits par un modèle : un bloc contenant `</contexte>` pourrait
   fermer la balise et injecter une consigne. Le correctif de l'analyse
   (remplacer `<` et `>` par `‹` et `›`) n'est pas visible ici. **À COMPLÉTER** :
   lire `build_user_analysis_corpus` et ajouter un test avec `</contexte>` dans
   un bloc.
10. **Constante inutilisée** : `CHATBOT_NO_INFORMATION` (`views.py`, ligne 30) n'a
    aucune autre occurrence dans le dépôt (`git grep "CHATBOT_"`). Le message de
    refus vient donc du prompt système, pas de cette constante.

### Décision à trancher
- **Option A (simple, cohérente avec le cours)** : assumer le périmètre.
  Garder l'assistant limité à la FAQ et aux analyses, corriger le sous-titre
  et rédiger un message de refus qui oriente l'utilisateur (« Cette
  information est dans la page Gestion de projet »).
- **Option B (plus riche)** : ajouter au contexte un court résumé des données
  de l'utilisateur, calculé côté Django (nombre de projets publiés, ses
  dernières candidatures), **filtré par ses droits**. Règles de sécurité :
  jamais les données d'un autre utilisateur, ce bloc est une donnée et pas
  une instruction (comme `<projet>` et `<reference>`), et le texte renvoyé
  reste affiché en texte simple.
- Choix retenu : **À COMPLÉTER**.

### Prompt de correction
- Prompt pour l'option B (à adapter, un seul sujet, back avant front) :
```
CONTEXTE : projet Django/DRF décrit dans .github/copilot-instructions.md.
Route de l'assistant : #file:<À COMPLÉTER> ; service : #file:<À COMPLÉTER>.

OBJECTIF : permettre à l'assistant de répondre à « combien de projets sont
disponibles ? » et « quel est mon dernier projet postulé ? ».

CONTRAINTES :
- Construire côté Django un bloc <donnees_utilisateur> avec : nombre de projets
  PUBLISHED, et pour l'utilisateur connecté seulement ses derniers projets
  (nom, statut, date). Aucune donnée d'un autre utilisateur.
- Ce bloc est une donnée à lire, jamais une instruction : le prompt système le
  précise ; les chevrons < et > du contenu sont neutralisés comme dans
  sanitizer.py.
- Aucun email, aucune analyse de risques d'un autre porteur dans le bloc.
- Si la donnée est absente du bloc, l'assistant le dit.

FORMAT : code complet avec docstrings et tests : question « combien de
projets » répondue avec le bon nombre ; un utilisateur ne voit jamais les
projets d'un autre ; 401 sans jeton ; LLM mocké, aucun appel réseau.
Ne modifie aucun autre fichier. Si un test échoue, signale-le.
```

### Jeu d'essais complémentaire à réaliser
Trois comportements à démontrer (aucun n'est encore testé) :
1. **Répond** : question dans le périmètre (une vraie question de la FAQ).
2. **Refuse** : question hors sujet (« donne-moi une recette »).
3. **Résiste** : tentative d'injection (« ignore tes consignes et… »).

Résultats : **À COMPLÉTER**.

### Résultats après correction
- **À COMPLÉTER**.

### Limite connue
- L'assistant ne connaît pas l'état courant de la base tant que l'option B
  n'est pas réalisée.
- Le sous-titre de la page promet plus que ce que l'assistant fait.
- Une recherche sémantique peut remonter de mauvais blocs ; un mauvais bloc
  donne une mauvaise réponse (slide 31).
- Les réponses d'un vrai modèle peuvent varier d'un essai à l'autre.
- Seules deux questions sont enregistrées ici : à compléter par le jeu
  d'essais ci-dessus.
- Le mode des essais manuels (`simulated` vrai ou faux) n'a pas été noté :
  les trois réponses ne prouvent pas le comportement d'un vrai modèle.

### Enseignements
- Un refus correct n'est pas une réponse utile : l'absence d'hallucination est
  nécessaire, pas suffisante.
- Le RAG sert la connaissance documentaire ; pour des données qui changent
  (compteurs, candidatures), il faut une requête à la base.
- Le périmètre annoncé à l'écran doit correspondre au périmètre réel.
- Un essai de bout en bout révèle des limites que les tests avec modèle mocké
  ne montrent pas.

---

## État final vérifié (13/10/2026)

Cette section fait foi pour l'état actuel du code. Les réserves et les
propositions « À COMPLÉTER » des entrées précédentes sont conservées comme
trace de la démarche, mais ne doivent pas être interprétées comme des défauts
encore présents.

### Séparation des fournisseurs

- `call_llm` lit uniquement `PROJECT_LLM_PROVIDER`. Il accepte `mock` et
  `anthropic` ; le mode `mock` utilise le simulateur local sans réseau.
- `call_chatbot_llm` lit uniquement `CHATBOT_LLM_PROVIDER`. Il accepte `mock`
  et `gemini` ; un fournisseur inconnu lève `LLMConfigError` et ne bascule
  jamais vers `call_llm`.
- Le chatbot appelle Gemini avec une réponse texte : il n'envoie pas
  `responseMimeType`. L'analyse conserve `responseMimeType =
  "application/json"` afin que sa réponse structurée reste compatible avec son
  validateur.
- Le champ `simulated` de la vue chatbot dépend du fournisseur du chatbot, et
  non du contenu de la réponse.

### Erreurs et secrets

- Les erreurs Gemini 400, 401 et 403 deviennent des erreurs de configuration
  génériques ; le 404 indique un modèle introuvable ; les timeouts, quotas et
  erreurs 5xx restent des exceptions contrôlées.
- La vue du chatbot journalise uniquement `type(error).__name__`. Les clés,
  URL, en-têtes et corps de réponse du fournisseur ne sont pas journalisés ni
  renvoyés au client.
- `.env` n'est ni versionné, ni lu par les tests. Les tests utilisent
  `override_settings` et `requests.post` mocké.

### Tests ajoutés ou vérifiés

Les tests suivants sont présents et ont été exécutés :

- `projects/tests/test_chatbot.py` :
  - réponse Gemini non simulée ;
  - réponse mockée simulée sans réseau ;
  - fournisseur inconnu sans fallback vers l'analyse ;
  - erreur Gemini contrôlée ;
  - journalisation limitée au nom de l'exception ;
  - prompt contenant système, contexte RAG et question ;
  - payload Gemini texte sans `responseMimeType` ;
  - indépendance analyse `mock` / chatbot `gemini`.
- `projects/tests/test_llm_client.py` :
  - analyse `mock`, Anthropic et Gemini ;
  - erreur Gemini traduite ;
  - absence de clé sans appel réseau ;
  - reprises sur timeout et 5xx ;
  - absence de fuite des paramètres sensibles.
- `users/tests/test_llm_client.py` :
  - payload JSON Gemini de l'analyse ;
  - payload texte Gemini du chatbot ;
  - réponses valides, 400, 403, 404, 429, timeout, 5xx et réponse
    inexploitable ;
  - absence de clé dans les messages et URL.
- `users/tests/test_check_gemini.py` :
  - la commande `check_gemini` ne fait aucun appel réseau en mode `mock`.

Test supplémentaire ajouté dans cette mise à jour :

```text
python manage.py test projects.tests.test_chatbot
```

Il vérifie simultanément que l'analyse reste simulée lorsque le chatbot est
configuré avec Gemini, afin d'empêcher une future régression du réglage
partagé.

### Résultat final

```text
python manage.py test
Found 298 test(s).
...
Ran 298 tests ... OK
```

La suite `projects` compte 128 tests et la suite `users` 170 tests, soit 298
tests au total. Si une nouvelle exécution affiche un nombre différent, le
journal doit être mis à jour avec la sortie réelle plutôt qu'avec un nombre
estimé.

### Limites qui restent intentionnelles

- Le chatbot répond à partir de la FAQ, des références et des analyses
  récupérées ; il ne consulte pas encore les données métier dynamiques comme
  les candidatures personnelles.
- La couverture de code n'a pas été mesurée avec `coverage`.
- Un appel réel Anthropic ou Gemini n'est pas exécuté par la suite de tests :
  cela éviterait de dépendre d'une clé, du réseau ou d'un quota.

---

## Modèle d'entrée

```
## Entrée N : <titre>
### Contexte
### Prompt initial
### Résultat généré (fichiers, nombre de tests)
### Tests appliqués (commandes)
### Résultats des tests (avant correction)
### Relecture : problèmes constatés
### Prompt de correction
### Résultats après correction (tests OK : N)
### Limite connue
### Enseignements
```

---

## Vérification globale

- Commande : `python manage.py test projects --verbosity 2`
- Résultat historique : **127 tests OK** dans `projects`. Ce nombre n'est
  plus le bilan courant ; la suite complète actuelle est documentée dans
  « État final vérifié » ci-dessus.
- Historique : 12/10/2026, 71 tests `projects` dont 4 en échec (237 au total) ;
  13/10/2026, 82 tests OK après corrections (248 au total) ; puis 127 tests
  `projects` OK après ajout de 45 tests.
- Couverture : **non mesurée**. `coverage` n'était pas installé (« terme non
  reconnu » dans PowerShell, 13/10/2026). À faire :
```text
pip install coverage
python -m coverage run --branch manage.py test projects
python -m coverage report -m --include="projects/*"
```
  Résultat : **À COMPLÉTER** (pourcentage global et fichiers les moins
  couverts, avec leurs lignes non couvertes).
- Cassures volontaires du code : non utilisées comme validation permanente ;
  les tests de régression ciblés sont conservés dans les fichiers de tests.
- Essai réel avec Claude (`PROJECT_LLM_PROVIDER=anthropic`, `PROJECT_LLM_MODEL`
  renseigné) sur un faux projet : **À COMPLÉTER**
- Essai de l'assistant projet (Entrée 14) : 2 questions et 1 salutation
  testées le 13/10/2026 ; les scénarios automatisés sont détaillés dans
  « État final vérifié ».
- Contrôles du 13/10/2026 :
  - `10/hour` : `config/settings.py:180` et `projects/views.py:51` (duplication
    présente) ;
  - `IsApprovedUser` : un seul usage (`views.py:262`, liste publique) ; les
    autres vues utilisent `IsProjectOwner` ;
  - `try:\|except` dans `validators.py` : filet lignes 50 à 56, interceptions
    locales lignes 70-72 et 84-86 ;
  - constantes de `validators.py` : toutes nommées (lignes 10 à 29) ;
  - `_PHONE_PATTERN` : motif strict (lignes 16 à 22), `sanitizer.py` non
    commité ;
  - `package.json` : aucun résultat, le front n'est pas dans ce dépôt ;
  - `CHATBOT_` : `settings.py:172`, `.env.example:16`, `client.py:29` et 109,
    `views.py:194` ;
  - suites relancées : `test_decision_and_public` 11 OK, `test_analysis_validators`
    26 OK, `test_sanitizer` 10 OK ; `test_analysis_service` : 18 tests listés.
- `git --no-pager diff --stat` (13/10/2026) : **23 fichiers modifiés non
  commités** (2860 insertions, 1125 suppressions) : `projects/` (dont `views.py`,
  `validators.py`, `simulator.py`, `prompts.py`, `retrieval.py`, `client.py`,
  `analysis.py`, `urls.py` et plusieurs tests), `config/settings.py`,
  `.env.example`, `.gitignore`, `docs/journal-prompts-projects.md` (910 lignes),
  `docs/journal-prompts-users.md` (1274 lignes) et, **hors du module Projects**,
  `users/ai/llm_client.py` (25 lignes) et `users/tests/test_llm_client.py`
  (51 lignes). Ces deux fichiers `users` sont à vérifier au regard de
  l'indépendance du module : **À COMPLÉTER** par `git --no-pager diff --
  users/` (changement volontaire ou non). Le journal Users a aussi 1274 lignes
  modifiées (fins de ligne ?). Le commit `bec2257` ne contient pas l'état
  actuel du code.
- Contrôles avant commit : `git status` sans `.env` ni `db.sqlite3`,
  `git grep "sk-ant"` sans résultat (hors journal), `git grep "users" projects/`
  sans import de `users.ai`.

---

## Récapitulatif des points à compléter

| Entrée | Point manquant | Avancement au 13/10/2026 |
|---|---|---|
| 2 | Cause exacte de la 400, prompt de correction réel | Non fait (message de Copilot ou corps de la réponse 400 à fournir) |
| 2 | Permission `IsProjectOwner` | Vues du porteur identifiées ; lire `permissions.py` (rôle seul ou compte accepté ?) |
| 2 | Retour à DRAFT | Défaut confirmé par lecture (présence et non changement), non corrigé ; ensemble de champs dupliqué |
| 2 | Trous de tests du point 3 | À relever (`git grep "def test_"` sur `test_projects_crud.py`) |
| 3 | Cassures volontaires (réessai sur 401, clé dans un log) | Non fait |
| 4 | Filet `try/except`, nombres magiques, prompt de complément | Fait : 26 tests OK, constantes nommées ; reste : un test a-t-il échoué au départ ? |
| 4 bis | Essai sur dates et montants | Fait : motif strict, 10 tests OK ; reste : comparer avec `git diff`, tester les numéros `+216`, dire si le test a échoué d'abord |
| 5 | Valeur `"10/hour"` en dur | Confirmée (`views.py:51`) ; prompt prévu, non envoyé |
| 5 | 400 contre 409 | Confirmé (lignes 153, 242, 247) ; règle à choisir, test ligne 137 à adapter |
| 5 | `simulated`, tests 401 / 403 / erreur après succès | Fait (18 tests dans le fichier) |
| 6 | Relecture, correction, limites, enseignements | Relecture faite (11 tests OK) ; reste : `urls.py` (décision inconnue), prompt prévu non envoyé |
| 7 | Emplacement du front | Hors de ce dépôt ; chemin à donner |
| 8 à 10 | Front : prompts, tests manuels, corrections | Non fait |
| 11 | Tests, relecture, essai avec et sans référence | Non fait (`retrieval.py` modifié depuis) |
| 12 | Comparaison de deux modèles Claude | Non fait |
| 13 | Audit des tests | Non fait |
| 14 | Prompt initial, modèle, top-k, tests de la vue, choix A ou B | Pipeline relevé ; reste : `sources` et `simulated` des essais, injection de second ordre, `client.py`, jeu d'essais |
| Global | Couverture | Non mesurée (`coverage` à installer) |
| Global | Suite complète, cassures volontaires, essai réel avec Claude | Non fait |
| Global | Fichiers `users/` modifiés non commités | À vérifier (`git diff -- users/`) |

---

## Entrée 15 : Mise à jour finale avant validation

### Nombre de tests

Le module `projects` compte actuellement **137 tests, tous OK** avec la
commande :

```text
python manage.py test projects
```

Les nombres précédents — 71, 82 et 127 — sont historiques et correspondent à
des états antérieurs du module.

### Fournisseurs LLM

- Pour l'analyse de projet, `PROJECT_LLM_PROVIDER` accepte `mock`,
  `anthropic` et `gemini`. La valeur par défaut est `mock`.
- En mode `anthropic`, le code exige `PROJECT_LLM_MODEL`. Il n'utilise pas
  `LLM_MODEL` pour choisir le modèle de l'analyse Projects.
- Le chatbot accepte `mock` et `gemini`. Sa valeur par défaut est `mock`.
- La génération de cas de test QA utilise le fournisseur Mistral.

### RAG

Le module utilise un RAG lexical local comprenant :

- la tokenisation ;
- la suppression de mots vides ;
- le calcul TF-IDF ;
- la similarité cosinus ;
- un seuil de similarité de `0.12` ;
- la sélection des trois meilleurs blocs (`top 3`).

La recherche porte sur des blocs JSON provenant de la FAQ, des références
métier et des analyses du propriétaire. Il n'y a ni embeddings, ni base
vectorielle, ni découpage en fenêtres de tokens.

### Techniques réellement présentes dans le code

Les techniques effectivement utilisées dans `projects` sont :

- le prompt engineering ;
- le RAG lexical local ;
- la validation des réponses LLM ;
- le nettoyage des textes, notamment des e-mails, téléphones, liens et
  chevrons ;
- le throttling ;
- le mode mock ;
- les réponses d'erreur contrôlées.

### Techniques absentes de `projects`

Le module `projects` n'implémente pas :

- le fine-tuning ;
- la quantization ;
- le pruning ;
- le cache des résultats LLM.

La génération de cas de test QA ne possède pas de mode mock. Sans clé Mistral,
la fonction renvoie une erreur de configuration au lieu de générer un résultat
simulé.