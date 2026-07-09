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
    "pc_lanes",
    "threads",
    "pcs",
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


def seed_pc(slug="kubo", name="Ishimaru Kubo"):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO pcs (slug, name) VALUES (%s, %s) RETURNING id, slug, name",
            (slug, name),
        )
        row = dict(cur.fetchone())
    conn.close()
    return row


def seed_thread(thread_id="thread-kubo-1", title="Hasami Tower Ascendant", status="active", factions=None):
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO threads (id, title, status, factions) VALUES (%s, %s, %s, %s)",
            (thread_id, title, status, factions or []),
        )
    conn.close()


def test_list_pc_lanes_includes_pcs_without_a_lane():
    seed_pc()
    res = client.get("/api/pc-lanes")
    assert res.status_code == 200
    lanes = res.json()
    assert len(lanes) == 1
    assert lanes[0]["has_lane"] is False
    assert lanes[0]["status"] == "active"
    assert lanes[0]["owned_threads"] == []


def test_get_lane_404_before_created():
    seed_pc()
    res = client.get("/api/pcs/kubo/lane")
    assert res.status_code == 404


def test_upsert_lane_creates_then_updates():
    seed_pc()
    res = client.put("/api/pcs/kubo/lane", json={"goal": "Rejoin the Hasami Tower", "status": "active"})
    assert res.status_code == 200
    body = res.json()
    assert body["goal"] == "Rejoin the Hasami Tower"
    assert body["has_lane"] is True

    res = client.put("/api/pcs/kubo/lane", json={"goal": "Reconcile with the Tower", "status": "stalled"})
    assert res.status_code == 200
    body = res.json()
    assert body["goal"] == "Reconcile with the Tower"
    assert body["status"] == "stalled"

    # still only one lane row for this PC (upsert, not duplicate insert)
    res = client.get("/api/pc-lanes")
    assert len(res.json()) == 1


def test_upsert_lane_rejects_invalid_status():
    seed_pc()
    res = client.put("/api/pcs/kubo/lane", json={"status": "not-a-real-status"})
    assert res.status_code == 422


def test_lane_surfaces_owned_threads_readonly():
    pc = seed_pc()
    seed_thread(factions=[pc["name"]])
    seed_thread(thread_id="thread-other", title="Unrelated Thread", factions=["Someone Else"])

    res = client.get("/api/pc-lanes")
    assert res.status_code == 200
    lane = res.json()[0]
    assert len(lane["owned_threads"]) == 1
    assert lane["owned_threads"][0]["title"] == "Hasami Tower Ascendant"
