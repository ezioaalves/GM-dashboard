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


from gm_dashboard import npcs_router


class FakePushRelay:
    def __init__(self):
        self.fail = False
        # Pre-populated so refresh-only tests (which never call push/execute_js first)
        # can still `get()` this actor.
        self.actors: dict[str, dict] = {
            "Actor.pushed1": {"system": {"abilities": {"str": {"value": 99}}}}
        }

    def execute_js(self, script: str) -> dict:
        if self.fail:
            return {"ok": False, "error": "relay down"}
        uuid = "Actor.pushed1"
        self.actors[uuid] = {"system": {"abilities": {"str": {"value": 99}}}}
        return {"ok": True, "uuid": uuid}

    def get(self, uuid: str) -> dict:
        return self.actors[uuid]


@pytest.fixture
def fake_push_relay(monkeypatch):
    relay = FakePushRelay()
    monkeypatch.setattr(npcs_router, "load_relay_client", lambda env="test": relay)
    return relay


def test_push_npc_creates_actor_and_locks(fake_push_relay):
    _insert_npc()
    res = client.post("/api/npcs/hayai/foundry/push", json={"env": "test"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["foundry_actor_id"] == "Actor.pushed1"

    npc = client.get("/api/npcs/hayai").json()
    assert npc["foundry_actor_id_test"] == "Actor.pushed1"
    assert npc["foundry_sync_locked"] is True


def test_push_npc_second_time_returns_409(fake_push_relay):
    _insert_npc()
    client.post("/api/npcs/hayai/foundry/push", json={"env": "test"})
    res = client.post("/api/npcs/hayai/foundry/push", json={"env": "test"})
    assert res.status_code == 409


def test_push_npc_with_existing_actor_id_returns_409(fake_push_relay):
    _insert_npc(foundry_actor_id_test="Actor.already")
    res = client.post("/api/npcs/hayai/foundry/push", json={"env": "test"})
    assert res.status_code == 409


def test_push_npc_relay_failure_returns_502(fake_push_relay):
    fake_push_relay.fail = True
    _insert_npc()
    res = client.post("/api/npcs/hayai/foundry/push", json={"env": "test"})
    assert res.status_code == 502

    npc = client.get("/api/npcs/hayai").json()
    assert npc["foundry_sync_locked"] is False
    assert npc["foundry_actor_id_test"] is None


def test_refresh_npc_stages_review_when_stats_differ(fake_push_relay):
    _insert_npc(foundry_actor_id_test="Actor.pushed1", foundry_sync_locked=True)
    res = client.post("/api/npcs/hayai/foundry/refresh", json={"env": "test"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["changed"] is True
    assert body["review_id"]

    review = client.get(f"/api/sync/reviews/{body['review_id']}")
    assert review.status_code == 200
    assert review.json()["review_type"] == "npc_import"
    assert review.json()["target_type"] == "npc"
    assert review.json()["proposed_changes"]["stats"]["abilities"]["str"] == 99


def test_refresh_npc_no_diff_creates_no_review(fake_push_relay):
    _insert_npc(
        foundry_actor_id_test="Actor.pushed1",
        foundry_sync_locked=True,
        stats={"abilities": {"str": 99}, "naruto_stats": {}},
    )
    res = client.post("/api/npcs/hayai/foundry/refresh", json={"env": "test"})
    assert res.status_code == 200
    assert res.json() == {"changed": False}


def test_refresh_npc_without_actor_id_returns_404(fake_push_relay):
    _insert_npc()
    res = client.post("/api/npcs/hayai/foundry/refresh", json={"env": "test"})
    assert res.status_code == 404
