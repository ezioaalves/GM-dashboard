from __future__ import annotations

import os
import pytest
import psycopg2
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


@pytest.fixture(autouse=True)
def restore_combat_type_entry_1():
    yield
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE generator_entries e
            SET name = 'Skirmish',
                description = 'The most common and reliable type of combat. Fun and straightforward, but can become repetitive without clear objectives.'
            FROM generator_tables t
            WHERE e.table_id = t.id AND t.key = 'combat_type' AND e.roll = 1
            """
        )
    conn.close()


def test_list_generator_tables_includes_seeded_entries():
    res = client.get("/api/generator/tables")
    assert res.status_code == 200
    body = res.json()
    keys = {t["key"] for t in body}
    assert keys == {"combat_type", "combat_objective", "combat_tricks", "mode_tag"}
    combat_type = next(t for t in body if t["key"] == "combat_type")
    assert combat_type["die"] == "d8"
    assert len(combat_type["entries"]) == 8
    assert combat_type["entries"][0]["name"] == "Skirmish"


def test_roll_returns_one_entry_and_writes_nothing():
    before = client.get("/api/generator/tables").json()
    res = client.post("/api/generator/tables/combat_tricks/roll")
    assert res.status_code == 200
    body = res.json()
    assert 1 <= body["roll"] <= 10
    assert body["name"]
    after = client.get("/api/generator/tables").json()
    assert before == after


def test_roll_unknown_table_404():
    res = client.post("/api/generator/tables/nonexistent/roll")
    assert res.status_code == 404


def test_patch_generator_entry():
    res = client.patch("/api/generator/tables/combat_type/entries/1", json={
        "name": "Skirmish (Homebrew)", "description": "Reworded for Kanigakure.",
    })
    assert res.status_code == 200
    assert res.json()["name"] == "Skirmish (Homebrew)"

    body = client.get("/api/generator/tables").json()
    combat_type = next(t for t in body if t["key"] == "combat_type")
    assert combat_type["entries"][0]["name"] == "Skirmish (Homebrew)"


def test_patch_generator_entry_unknown_roll_404():
    res = client.patch("/api/generator/tables/combat_type/entries/999", json={"name": "x"})
    assert res.status_code == 404
