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
    "feedback_action_items",
    "feedback_entries",
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


def test_list_feedback_empty():
    res = client.get("/api/feedback")
    assert res.status_code == 200
    assert res.json() == []


def test_create_feedback_with_action_items_and_cascade_delete():
    res = client.post("/api/feedback", json={
        "session_number": 12,
        "cadence": "quick_check",
        "players_present": "Ikazuchi, Kubo, Dan, Suigin",
        "more_of": "Combat encounters with terrain tricks",
        "less_of": "Long social scenes without a clock",
        "clarify": "Whether downtime crafting costs Chakra pool or gold",
    })
    assert res.status_code == 201
    entry = res.json()
    assert entry["action_items"] == []

    res = client.post(f"/api/feedback/{entry['id']}/action-items", json={
        "item": "Confirm crafting cost rule", "owner": "GM", "follow_up": "Post in the group chat",
    })
    assert res.status_code == 201
    item = res.json()

    detail = client.get(f"/api/feedback/{entry['id']}").json()
    assert len(detail["action_items"]) == 1

    res = client.patch(f"/api/feedback/{entry['id']}/action-items/{item['id']}", json={"status": "done"})
    assert res.status_code == 200
    assert res.json()["status"] == "done"

    res = client.delete(f"/api/feedback/{entry['id']}")
    assert res.status_code == 200
    assert client.get(f"/api/feedback/{entry['id']}").status_code == 404

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM feedback_action_items WHERE feedback_id = %s", (entry["id"],))
        assert cur.fetchone()[0] == 0
    conn.close()


def test_create_feedback_rejects_invalid_cadence():
    res = client.post("/api/feedback", json={"cadence": "monthly"})
    assert res.status_code == 422


def test_overdue_flips_true_past_threshold_and_excludes_private_checkin():
    for n in range(1, 9):
        seed_session(n)

    # no feedback ever recorded -> both quick_check and arc_review overdue
    res = client.get("/api/feedback/overdue")
    assert res.status_code == 200
    cadences = {row["cadence"] for row in res.json()}
    assert cadences == {"quick_check", "arc_review"}

    # record a quick_check at session 8 (latest) -> no longer overdue
    client.post("/api/feedback", json={"session_number": 8, "cadence": "quick_check"})
    res = client.get("/api/feedback/overdue")
    cadences = {row["cadence"] for row in res.json()}
    assert "quick_check" not in cadences
    assert "arc_review" in cadences

    # private_checkin entries never count toward any cadence's overdue check
    client.post("/api/feedback", json={"session_number": 1, "cadence": "private_checkin"})
    res = client.get("/api/feedback/overdue")
    cadences = {row["cadence"] for row in res.json()}
    assert "private_checkin" not in cadences
