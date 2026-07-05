from __future__ import annotations

import os
import pytest
import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from gm_dashboard.api import app

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
)

client = TestClient(app)

TABLES_TO_CLEAN = [
    "adventure_cast",
    "adventure_encounters",
    "adventure_clock_links",
    "adventure_rewards",
    "adventure_pc_pressure",
    "session_adventures",
    "adventures",
    "npcs",
    "pcs",
    "clocks",
    "threads",
    "sessions",
]


def _connect():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


@pytest.fixture(autouse=True)
def clean_tables():
    conn = _connect()
    with conn.cursor() as cur:
        for table in TABLES_TO_CLEAN:
            cur.execute(f"DELETE FROM {table}")
    conn.close()
    yield
    conn = _connect()
    with conn.cursor() as cur:
        for table in TABLES_TO_CLEAN:
            cur.execute(f"DELETE FROM {table}")
    conn.close()


def seed_pc(slug="ikazuchi", name="Ikazuchi"):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO pcs (slug, name) VALUES (%s, %s) RETURNING id, slug, name",
            (slug, name),
        )
        row = dict(cur.fetchone())
    conn.close()
    return row


def seed_npc(slug="test-npc", name="Test NPC"):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO npcs (slug, name) VALUES (%s, %s) RETURNING id, slug, name",
            (slug, name),
        )
        row = dict(cur.fetchone())
    conn.close()
    return row


def test_migration_smoke_generator_tables_seeded():
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("SELECT key FROM generator_tables ORDER BY key")
        keys = [r[0] for r in cur.fetchall()]
    conn.close()
    assert keys == ["combat_objective", "combat_tricks", "combat_type", "mode_tag"]


def test_list_adventures_empty():
    res = client.get("/api/adventures")
    assert res.status_code == 200
    assert res.json() == []


def test_create_and_get_adventure():
    res = client.post("/api/adventures", json={
        "title": "The Archive Route",
        "pitch": "The 13th Tanto must expose a false training record before Kanimaru's version becomes public truth.",
        "mode": "investigation",
        "current_arc": "Training Arc",
    })
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "The Archive Route"
    assert body["status"] == "draft"
    assert body["stakes"] == {}
    assert body["spine"] == []

    res = client.get(f"/api/adventures/{body['id']}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["pitch"].startswith("The 13th Tanto")
    assert detail["pc_pressure"] == []
    assert detail["rewards"] == []
    assert detail["clock_links"] == []
    assert detail["encounters"] == []
    assert detail["cast"] == []
    assert detail["sessions"] == []


def test_get_adventure_not_found():
    res = client.get("/api/adventures/999999")
    assert res.status_code == 404


def test_patch_adventure_updates_jsonb_fields():
    create = client.post("/api/adventures", json={"title": "Court Pressure"}).json()
    res = client.patch(f"/api/adventures/{create['id']}", json={
        "status": "ready",
        "stakes": {"immediate": "A hostage is at risk", "if_ignore": "The hostage is moved"},
    })
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["stakes"]["immediate"] == "A hostage is at risk"


def test_delete_adventure():
    create = client.post("/api/adventures", json={"title": "One-shot"}).json()
    res = client.delete(f"/api/adventures/{create['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}
    assert client.get(f"/api/adventures/{create['id']}").status_code == 404
