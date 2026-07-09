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

TABLES_TO_CLEAN = [
    "risks",
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


def seed_session(number):
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sessions (number, name, status) VALUES (%s, %s, %s)",
            (number, f"Session {number}", "played"),
        )
    conn.close()


def test_list_risks_empty():
    res = client.get("/api/risks")
    assert res.status_code == 200
    assert res.json() == []


def test_create_and_get_risk():
    res = client.post("/api/risks", json={
        "title": "Suigin is the only source on the poison-crafting research",
        "description": "If Suigin's player is absent, the thread stalls entirely.",
        "likelihood": "medium",
        "mitigation": "Cross-reference with an NPC contact as a backup source.",
        "contingency": "GM narrates a summarized update in-fiction if needed.",
    })
    assert res.status_code == 201
    risk = res.json()
    assert risk["likelihood"] == "medium"
    assert risk["status"] == "open"

    res = client.get(f"/api/risks/{risk['id']}")
    assert res.status_code == 200
    assert res.json()["title"] == risk["title"]


def test_create_risk_rejects_invalid_likelihood():
    res = client.post("/api/risks", json={"title": "Bad risk", "likelihood": "extreme"})
    assert res.status_code == 422


def test_patch_and_delete_risk():
    risk = client.post("/api/risks", json={"title": "Schedule risk"}).json()

    res = client.patch(f"/api/risks/{risk['id']}", json={"status": "mitigated"})
    assert res.status_code == 200
    assert res.json()["status"] == "mitigated"

    res = client.delete(f"/api/risks/{risk['id']}")
    assert res.status_code == 200
    assert client.get(f"/api/risks/{risk['id']}").status_code == 404


def test_mark_reviewed_and_stale_filter():
    for n in range(1, 6):
        seed_session(n)

    risk = client.post("/api/risks", json={"title": "Single point of failure"}).json()
    res = client.post(f"/api/risks/{risk['id']}/mark-reviewed", json={"session_number": 1})
    assert res.status_code == 200
    assert res.json()["last_reviewed_session"] == 1

    # reviewed at session 1, latest session is 5 -> 4 sessions stale
    res = client.get("/api/risks/stale", params={"threshold": 3})
    assert res.status_code == 200
    assert any(r["id"] == risk["id"] for r in res.json())

    res = client.get("/api/risks/stale", params={"threshold": 10})
    assert res.status_code == 200
    assert not any(r["id"] == risk["id"] for r in res.json())
