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
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn gm_dashboard.api:app --app-dir backend --reload
```

Optional local Postgres for dashboard structured state:

```bash
docker compose up -d postgres
```

Run database migrations from the repo root. `backend/alembic/` is the
canonical migration tree; the root `alembic.ini` is the only supported Alembic
config.

```bash
PYTHONPATH=backend alembic -c alembic.ini upgrade head
```

Alembic owns the schema end-to-end: migration `001` codifies the initial
schema and every table since is an Alembic migration, so `upgrade head` builds
a complete database from empty (`backend/gm_dashboard/db/schema.sql` is kept
as a historical reference only and is not applied). Additive Alembic
migrations are the supported path for the core spine and review-gated
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

gm-dashboard is its own repository, checked out as a gitignored sibling folder
at the Kaihou vault repo root. Set `KAIHOU_VAULT_ROOT` to the Kaihou vault
checkout path (it no longer auto-detects from the app's own location, since
the app and the vault are separate repos).

## Frontend

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api` to `https://gm.ezioalves.cloud` by default;
set `KAIHOU_DASHBOARD_API` only when intentionally targeting another server.

## Tests

```bash
python -m pytest backend/tests
npm test
```

## Deployment

See `DEPLOY.md` for the VPS deployment runbook and GitHub Actions pipeline.
