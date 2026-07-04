# Kaihou GM Dashboard

Private GM cockpit for prep, note capture, and session recovery.

The current source-boundary rules live in
`docs/superpowers/system-definition/`. Markdown remains the long-form prose and
source-artifact layer for session logs, prep, lore files, mechanics, and
operational tickets until reviewed import/cutover. Postgres owns reviewed
structured dashboard state: tickets after accepted import, lore projections and
graph records, threads, sessions, scenes, sync reviews, sync jobs, assets, and
Foundry mirror metadata.

## Backend

```bash
cd "Creation Zone/gm-dashboard"
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn gm_dashboard.api:app --app-dir backend --reload
```

Optional local Postgres for dashboard structured state:

```bash
cd "Creation Zone/gm-dashboard"
docker compose up -d postgres
```

Run database migrations from the dashboard root. `backend/alembic/` is the
canonical migration tree; the root `alembic.ini` is the only supported Alembic
config.

```bash
cd "Creation Zone/gm-dashboard"
PYTHONPATH=backend alembic -c alembic.ini upgrade head
```

The initial schema lives at `backend/gm_dashboard/db/schema.sql`. Additive
Alembic migrations are the supported path for the core spine and review-gated
crossings. Do not delete Markdown ticket, lore, session-log, asset, or Foundry
source artifacts as part of import; stage crossings through `sync_reviews` and
record apply attempts in `sync_jobs`.

Useful endpoints:

- `GET /api/cockpit/session`
- `POST /api/capture/session-note`
- `POST /api/capture/scene`
- `GET /api/search?q=haiiro`
- `GET /api/tickets`
- `GET /api/sync/freshness`
- `GET /api/sync/reviews`
- `POST /api/drafts/{id}/save`
- `GET /api/foundry/status`

The backend auto-detects the vault root from the app location. Set
`KAIHOU_VAULT_ROOT` to override it.

## Frontend

```bash
cd "Creation Zone/gm-dashboard"
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Tests

```bash
cd "Creation Zone/gm-dashboard"
python -m pytest backend/tests
npm test
```
