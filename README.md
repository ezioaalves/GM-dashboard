# Kaihou GM Dashboard

Private GM cockpit for prep, note capture, and session recovery.

The multi-vault source-boundary rules live in the sibling
`../agent-vault/superpowers/` documentation. The campaign vault owns prose,
prep, sessions, and assets; Postgres owns structured state, bindings, reviews,
jobs, and freshness; Foundry owns runtime mechanics and permissions. Crossings
are reviewed. Idea Inbox records are Dashboard-only operational material:
promoting an idea does not publish or synchronize it.

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

Set `KAIHOU_VAULT_ROOT` to the sibling `campaign-vault` checkout. Production
also mounts registered mechanics and agent source collections read-only.

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
npm run check
```

For a local integration database only, run
`POSTGRES_PASSWORD=kaihou_gm_dev docker compose --profile test up -d postgres`,
then migrate it with the matching `DATABASE_URL`. Never point tests at the VPS
database.

## Feature slices

New frontend work lives behind the typed API facade, the navigation registry,
shared UI controls, dedicated feature styles, and focused tests. Direct fetches
and inline feature layout styles are prohibited. Declare the owning surface for
every mutation; vault and Foundry writes must enter `sync_reviews` first.
Adopt this foundation next in Sync Center/Clocks, Session/Scene boards,
Campaign Health/Library, then remaining low-risk pages.

## Deployment

See `DEPLOY.md` for the VPS deployment runbook and GitHub Actions pipeline.
