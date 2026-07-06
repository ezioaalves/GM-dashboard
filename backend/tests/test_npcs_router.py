from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from gm_dashboard.api import app

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
)

client = TestClient(app)


def _connect():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _clean() -> None:
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM npcs")
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
        cur.execute("DELETE FROM lore_entities")
    conn.close()


@pytest.fixture(autouse=True)
def clean_tables():
    _clean()
    yield
    _clean()


def _insert_npc(**overrides) -> dict:
    base = {
        "slug": "hayai", "name": "Dattoumaru Hayai", "affiliation": None, "status": None,
        "img_path": None, "vault_path": "Lore/NPCs/Hayai_Sheet.md",
        "stats": {"abilities": {"str": 12}},
        "foundry_actor_id_test": None, "foundry_actor_id_prod": None,
        "foundry_sync_locked": False,
    }
    base.update(overrides)
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO npcs (
                  slug, name, affiliation, status, img_path, vault_path, stats,
                  foundry_actor_id_test, foundry_actor_id_prod, foundry_sync_locked
                )
                VALUES (
                  %(slug)s, %(name)s, %(affiliation)s, %(status)s, %(img_path)s, %(vault_path)s,
                  %(stats)s, %(foundry_actor_id_test)s, %(foundry_actor_id_prod)s,
                  %(foundry_sync_locked)s
                )
                RETURNING *
                """,
                {**base, "stats": psycopg2.extras.Json(base["stats"])},
            )
            return dict(cur.fetchone())
    finally:
        conn.close()


def test_get_npc_404_when_missing():
    res = client.get("/api/npcs/nobody")
    assert res.status_code == 404


def test_list_and_get_npc():
    _insert_npc()
    listed = client.get("/api/npcs")
    assert listed.status_code == 200
    assert [row["slug"] for row in listed.json()] == ["hayai"]

    got = client.get("/api/npcs/hayai")
    assert got.status_code == 200
    assert got.json()["name"] == "Dattoumaru Hayai"
    assert got.json()["stats"]["abilities"]["str"] == 12


def test_list_npcs_filters_by_status():
    _insert_npc(slug="active-one", status="active")
    _insert_npc(slug="retired-one", status="retired")
    res = client.get("/api/npcs?status=active")
    assert res.status_code == 200
    assert [row["slug"] for row in res.json()] == ["active-one"]


def test_sync_npcs_endpoint_calls_projection(tmp_path, monkeypatch):
    sheet = tmp_path / "Lore" / "NPCs" / "Hayai_Sheet.md"
    sheet.parent.mkdir(parents=True)
    sheet.write_text("---\nname: Dattoumaru Hayai\n---\n# Dattoumaru Hayai\n")
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_entities (slug, title, entity_type, source_path, review_status)
                VALUES ('hayai', 'Dattoumaru Hayai', 'npc', 'Lore/NPCs/Hayai_Sheet.md', 'accepted')
                """
            )
    finally:
        conn.close()

    res = client.post("/api/npcs/sync")
    assert res.status_code == 200
    assert res.json() == {"scanned": 1, "synced": 1, "errors": []}

    got = client.get("/api/npcs/hayai")
    assert got.status_code == 200
    assert got.json()["name"] == "Dattoumaru Hayai"
