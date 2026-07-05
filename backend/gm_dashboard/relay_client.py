from __future__ import annotations

from pathlib import Path

import requests


class RelayError(RuntimeError):
    """Relay unreachable, unconfigured, or returned an error payload."""


FOUNDRY_ENV = Path("Creation Zone/automation_scripts/foundry/.env")
TIMEOUT = 20


class RelayClient:
    def __init__(self, base_url: str, api_key: str, client_id: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client_id = client_id

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key}

    def _check(self, resp) -> dict:
        if resp.status_code >= 400:
            raise RelayError(f"relay HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def get(self, uuid: str) -> dict:
        resp = requests.get(
            f"{self.base_url}/get", headers=self._headers(),
            params={"uuid": uuid, "clientId": self.client_id}, timeout=TIMEOUT,
        )
        return self._check(resp).get("data") or {}

    def update(self, uuid: str, data: dict) -> dict:
        resp = requests.put(
            f"{self.base_url}/update", headers=self._headers(),
            params={"uuid": uuid, "clientId": self.client_id},
            json={"data": data}, timeout=TIMEOUT,
        )
        return self._check(resp)

    def search(self, query: str) -> list[dict]:
        resp = requests.get(
            f"{self.base_url}/search", headers=self._headers(),
            params={"query": query, "clientId": self.client_id}, timeout=TIMEOUT,
        )
        payload = self._check(resp)
        return payload.get("results") or payload.get("data") or []


def _read_env(vault_root: Path) -> dict[str, str]:
    env_path = vault_root / FOUNDRY_ENV
    if not env_path.exists():
        raise RelayError(f"foundry .env not found at {env_path}")
    out: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_relay_client(env: str = "test") -> RelayClient:
    from . import services

    vault_root = services.find_vault_root()
    values = _read_env(vault_root)
    # The vault's .env (Creation Zone/automation_scripts/foundry/.env) uses the
    # TEST_*/PROD_* prefix convention established by env_utils.py, not a
    # FOUNDRY_*/FOUNDRY_*_PROD suffix scheme. Support both so this keeps
    # working if the .env convention ever changes.
    prefix = "PROD_" if env == "prod" else "TEST_"
    suffix = "_PROD" if env == "prod" else ""
    base_url = (
        values.get(f"{prefix}RELAY_REST")
        or values.get(f"FOUNDRY_RELAY_REST{suffix}", "")
    )
    api_key = (
        values.get(f"{prefix}API_KEY")
        or values.get(f"FOUNDRY_API_KEY{suffix}", "")
    )
    if not base_url or not api_key:
        raise RelayError(f"relay credentials for env={env} are not configured")
    resp = requests.get(f"{base_url.rstrip('/')}/clients",
                        headers={"x-api-key": api_key}, timeout=TIMEOUT)
    if resp.status_code >= 400:
        raise RelayError(f"relay /clients HTTP {resp.status_code}")
    clients = resp.json() if isinstance(resp.json(), list) else resp.json().get("clients", [])
    if not clients:
        raise RelayError("no connected Foundry worlds on relay")
    client_id = clients[0].get("id") or clients[0].get("clientId")
    return RelayClient(base_url, api_key, client_id)
