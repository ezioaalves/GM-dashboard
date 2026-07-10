# Deploying gm-dashboard to the VPS

gm-dashboard runs on the same VPS as Foundry VTT (`foundry.ezioalves.cloud`),
behind that box's existing nginx, on `gm.ezioalves.cloud`. It ships as three
Docker Compose services (`postgres`, `backend`, `frontend`), built on the VPS
by the GitHub Actions pipeline on every push to `main`.

## One-time VPS setup

Run these on the VPS itself (SSH access required — not something this
repo's CI can do for you the first time).

1. **Clone this repo** to the deploy path (pick one, referenced below as
   `$VPS_DEPLOY_PATH`, e.g. `/opt/gm-dashboard`):

   ```bash
   git clone git@github.com:ezioaalves/GM-dashboard.git /opt/gm-dashboard
   ```

2. **Clone the Kaihou vault** — gm-dashboard reads/writes vault markdown via
   `KAIHOU_VAULT_ROOT`. This is a manual-pull mirror: re-run `git pull` here
   whenever you want the VPS to see your latest local vault edits. There is
   no automatic sync.

   ```bash
   git clone git@github.com:ezioaalves/Kaihou.git /opt/kaihou-vault
   ```

3. **Create the env file** at `/opt/gm-dashboard/.env` from
   `.env.production.example`, filling in a real `POSTGRES_PASSWORD` and
   confirming `KAIHOU_VAULT_ROOT=/opt/kaihou-vault`.

4. **First build and start:**

   ```bash
   cd /opt/gm-dashboard
   docker compose -f docker-compose.prod.yml up -d --build
   ```

5. **Proxy host in Nginx Proxy Manager** — the VPS does not run a host
   nginx; ports 80/443 belong to the Nginx Proxy Manager container
   (`proxy-app-1`, admin UI on port 81), which also fronts Foundry. The
   compose file attaches `backend`/`frontend` to NPM's external
   `proxy-tier` network, so NPM reaches them by container name. In the
   NPM admin UI:

   - **Proxy Host**: domain `gm.ezioalves.cloud`, scheme `http`, forward
     to `gm-dashboard-frontend` port `80`. Enable *Block Common Exploits*.
   - **Custom location** `/api`: scheme `http`, forward to
     `gm-dashboard-backend` port `8000`.
   - **SSL tab**: request a new Let's Encrypt certificate, enable *Force
     SSL*.
   - **Access List** (Basic Auth): create an access list with an
     Authorization user/password, *Satisfy Any*, and assign it to the
     proxy host so both the frontend and `/api` are covered.

6. **GitHub Actions secrets/variables** — in this repo's Settings → Secrets
   and variables → Actions, add:

   | Name | Type | Value |
   |---|---|---|
   | `VPS_HOST` | secret | VPS hostname/IP |
   | `VPS_USER` | secret | SSH user for deploys |
   | `VPS_SSH_KEY` | secret | Private key with access to the deploy user |
   | `VPS_DEPLOY_PATH` | variable | `/opt/gm-dashboard` (or wherever you cloned it) |

## Ongoing deploys

Push to `main`, or trigger manually via Actions → Deploy to VPS →
"Run workflow". The pipeline SSHes in and runs:

```bash
cd $VPS_DEPLOY_PATH
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
```

Postgres data persists in a named Docker volume (`gm-dashboard-postgres`)
independent of the app containers, so redeploys don't touch the database.

## Refreshing the vault on the VPS

The vault clone at `/opt/kaihou-vault` (or wherever `KAIHOU_VAULT_ROOT`
points) does **not** update automatically. Whenever you want the VPS-side
gm-dashboard to see fresh vault content:

```bash
cd /opt/kaihou-vault
git pull
```
