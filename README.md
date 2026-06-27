# Kaihou GM Dashboard

Private GM cockpit for prep, note capture, and session recovery.

Markdown remains canonical for session logs, tickets, lore, mechanics, and prep. The
backend reads and writes vault-relative Markdown paths; Postgres is reserved for app
internals such as users, draft workflow state, projections, sync jobs, Foundry links,
and later sheet-like structured records.

## Backend

```bash
cd "Creation Zone/gm-dashboard"
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn gm_dashboard.api:app --app-dir backend --reload
```

Optional local Postgres for app internals:

```bash
cd "Creation Zone/gm-dashboard"
docker compose up -d postgres
```

The initial schema lives at `backend/gm_dashboard/db/schema.sql`. The v1
cockpit endpoints are still Markdown-first; database-backed auth, durable draft
state, projections, sheet records, and sync jobs can be layered onto this schema.

Useful endpoints:

- `GET /api/cockpit/session`
- `POST /api/capture/session-note`
- `POST /api/capture/scene`
- `GET /api/search?q=haiiro`
- `GET /api/tickets`
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
