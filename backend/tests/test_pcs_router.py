from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from gm_dashboard import pcs_router
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
        cur.execute("DELETE FROM pcs")
        cur.execute("DELETE FROM lore_entities")
    conn.close()


@pytest.fixture(autouse=True)
def clean_tables():
    _clean()
    yield
    _clean()


def _insert_pc(**overrides) -> dict:
    base = {
        "slug": "suigin", "name": "Suigin", "player": "Alex",
        "stats": {"abilities": {"str": 14}},
        "foundry_actor_id_test": None, "foundry_actor_id_prod": None,
    }
    base.update(overrides)
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO pcs (slug, name, player, stats, foundry_actor_id_test, foundry_actor_id_prod)
                VALUES (%(slug)s, %(name)s, %(player)s, %(stats)s,
                        %(foundry_actor_id_test)s, %(foundry_actor_id_prod)s)
                RETURNING *
                """,
                {**base, "stats": psycopg2.extras.Json(base["stats"])},
            )
            return dict(cur.fetchone())
    finally:
        conn.close()


class FakePcRelay:
    def __init__(self):
        self.actors = {"Actor.pcprod1": {"system": {"abilities": {"str": {"value": 15}}}}}

    def get(self, uuid: str) -> dict:
        return self.actors[uuid]


@pytest.fixture
def fake_pc_relay(monkeypatch):
    relay = FakePcRelay()
    monkeypatch.setattr(pcs_router, "load_relay_client", lambda env="test": relay)
    return relay


def test_get_pc_404_when_missing():
    res = client.get("/api/pcs/nobody")
    assert res.status_code == 404


def test_list_and_get_pc():
    _insert_pc()
    listed = client.get("/api/pcs")
    assert listed.status_code == 200
    assert [row["slug"] for row in listed.json()] == ["suigin"]

    got = client.get("/api/pcs/suigin")
    assert got.status_code == 200
    assert got.json()["player"] == "Alex"


def test_sync_pcs_endpoint(tmp_path, monkeypatch):
    sheet = tmp_path / "Lore" / "Player_Characters" / "Suigin" / "Suigin_Sheet.md"
    sheet.parent.mkdir(parents=True)
    sheet.write_text("---\nname: Suigin\n---\n# Suigin\n")
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lore_entities (slug, title, entity_type, source_path, review_status)
                VALUES ('suigin', 'Suigin', 'pc',
                        'Lore/Player_Characters/Suigin/Suigin_Sheet.md', 'accepted')
                """
            )
    finally:
        conn.close()

    res = client.post("/api/pcs/sync")
    assert res.status_code == 200
    assert res.json() == {"scanned": 1, "synced": 1, "errors": []}
    assert client.get("/api/pcs/suigin").json()["name"] == "Suigin"


def test_refresh_pc_writes_stats_directly_no_review(fake_pc_relay):
    _insert_pc(foundry_actor_id_prod="Actor.pcprod1")
    res = client.post("/api/pcs/suigin/foundry/refresh", json={"env": "prod"})
    assert res.status_code == 200, res.text
    assert res.json()["refreshed"] is True
    assert res.json()["stats"]["abilities"]["str"] == 15

    pc = client.get("/api/pcs/suigin").json()
    assert pc["stats"]["abilities"]["str"] == 15

    reviews = client.get("/api/sync/reviews?review_type=pc_import")
    assert reviews.json() == []


def test_refresh_pc_without_actor_id_returns_404(fake_pc_relay):
    _insert_pc()
    res = client.post("/api/pcs/suigin/foundry/refresh", json={"env": "prod"})
    assert res.status_code == 404


def test_no_push_route_exists_for_pcs():
    _insert_pc()
    res = client.post("/api/pcs/suigin/foundry/push", json={"env": "prod"})
    assert res.status_code == 404
