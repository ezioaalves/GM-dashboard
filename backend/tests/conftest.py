from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def test_vault_root(tmp_path_factory):
    """Point the app at a throwaway vault with a configured Foundry env.

    Freshness reporting emits a high-priority integration item whenever the
    Foundry env file is missing; tests that exercise the unconfigured state
    monkeypatch it explicitly, so the shared baseline stays configured and
    deterministic across local runs and CI.
    """
    vault = tmp_path_factory.mktemp("kaihou-test-vault")
    env_file = vault / "Creation Zone" / "automation_scripts" / "foundry" / ".env"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text("FOUNDRY_URL=http://127.0.0.1:30000\n", encoding="utf-8")
    os.environ["KAIHOU_VAULT_ROOT"] = str(vault)
    yield vault
