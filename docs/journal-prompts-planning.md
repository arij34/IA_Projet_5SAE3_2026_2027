# Planning module journal

## Request

Add an isolated planning feature to Freelancy. A project owner provides only a project name, receives exactly three editable draft tasks, and saves the planning explicitly.

## Implemented

- Generation through the existing `users.ai.llm_client.call_llm` helper and `LLM_PROVIDER` setting. Only the project name is sent as user content.
- Markdown fence stripping, strict JSON/date/string validation, exactly three sequential generated tasks, and three realistic simulated fallback tasks on mock provider or generation failure.
- Draft UI with task editing, confirmed removal, modal task addition, field validation, and explicit save.
- Authenticated project-owner API for generation, atomic save, list/retrieve, task update, and task deletion.
- Saved planning list, reload-as-draft, and direct edit/delete actions for saved tasks.

## Models and ownership

- `PlanningProject`: name, creation timestamp, and owner.
- `Task`: project, name, description, start date, and end date; tasks are ordered by start date.
- The owner relation is an intentional addition to the requested fields so users cannot see or mutate another user's planning. The existing `projects` app was not changed.

## Endpoints

- `POST /api/planning/generate/`
- `GET|POST /api/planning/`
- `GET /api/planning/<id>/`
- `PUT|PATCH|DELETE /api/planning/<project_id>/tasks/<task_id>/`

## Files created

- Backend app: `planning/__init__.py`, `planning/apps.py`, `planning/models.py`, `planning/serializers.py`, `planning/views.py`, `planning/urls.py`, `planning/tests.py`.
- AI: `planning/ai/__init__.py`, `planning/ai/prompts.py`, `planning/ai/generation.py`.
- Migration: `planning/migrations/__init__.py`, `planning/migrations/0001_initial.py`.
- Frontend: `src/features/planning/PlanningPage.tsx`, `src/features/planning/planningApi.ts`, `src/features/planning/planning.css`.
- Documentation: `docs/journal-prompts-planning.md`.

## Existing source files modified

- `config/settings.py`: added `"planning",` to `INSTALLED_APPS`.
- `config/urls.py`: added `path("api/planning/", include("planning.urls")),`.
- `src/App.tsx`: added the `PlanningPage` import and `/planning` route under `ProjectOwnerRoute`.
- `src/components/Layout.tsx`: added the project-owner navigation link to `/planning`.

## Verification

- `python manage.py makemigrations planning`: created `planning.0001_initial` with only the two planning tables.
- `python manage.py migrate planning`: succeeded; only the new planning migration was applied. The existing SQLite database file `db.sqlite3` was updated with those tables.
- `python manage.py test planning`: 11 tests passed, covering generation/fallback, validation, persistence, ownership/permissions, and task update/deletion.
- `npm run build`: passed; TypeScript and Vite production build succeeded.
- The Vite build generated/updated `dist/index.html`, `dist/favicon.svg`, and hashed CSS/JS assets. TypeScript build cache files under `node_modules/.tmp` were also generated/updated.

## Limitations

- The fallback language is inferred from common French/English words in the project name; ambiguous names default to French.
- The saved-planning UI edits and deletes saved tasks directly through their endpoints. Loading a saved plan into the main form creates a new copy when saved.
