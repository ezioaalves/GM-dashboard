from __future__ import annotations

import os
import pytest
import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from gm_dashboard.api import app

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@localhost:54329/kaihou_gm"
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tables():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM scenes")
        cur.execute("DELETE FROM sessions")
    conn.close()
    yield
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM scenes")
        cur.execute("DELETE FROM sessions")
    conn.close()


def seed_session(number=1, name="Test Session"):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO sessions (number, name) VALUES (%s, %s) RETURNING id, number, name",
            (number, name),
        )
        row = cur.fetchone()
    conn.close()
    return dict(row)


def seed_scene(overrides=None):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    base = {"title": "Test Scene", "status": "Draft", "type": "Hard",
            "session_id": None, "description": "A test scene"}
    if overrides:
        base.update(overrides)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO scenes (title, status, type, session_id, description)
               VALUES (%(title)s, %(status)s, %(type)s, %(session_id)s, %(description)s)
               RETURNING id""",
            base,
        )
        row = cur.fetchone()
        base["id"] = row["id"]
    conn.close()
    return base


# --- Sessions ---

def test_list_sessions_empty():
    res = client.get("/api/sessions")
    assert res.status_code == 200
    assert res.json() == []


def test_create_session():
    res = client.post("/api/sessions", json={"number": 18, "name": "The Iron Keep"})
    assert res.status_code == 201
    data = res.json()
    assert data["number"] == 18
    assert data["name"] == "The Iron Keep"
    assert "id" in data


def test_list_sessions_returns_created():
    seed_session(number=17, name="Old session")
    seed_session(number=18, name="New session")
    res = client.get("/api/sessions")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    # Ordered by number DESC
    assert data[0]["number"] == 18


# --- Scenes ---

def test_list_scenes_empty():
    res = client.get("/api/scenes")
    assert res.status_code == 200
    assert res.json() == []


def test_create_scene():
    res = client.post("/api/scenes", json={"title": "Ambush", "type": "Hard", "status": "Draft"})
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Ambush"
    assert data["type"] == "Hard"
    assert data["status"] == "Draft"
    assert data["session_id"] is None


def test_create_scene_with_session():
    session = seed_session()
    res = client.post("/api/scenes", json={
        "title": "Council Scene", "type": "Soft", "status": "Ready",
        "session_id": session["id"],
    })
    assert res.status_code == 201
    assert res.json()["session_id"] == session["id"]


def test_list_scenes_returns_seeded():
    seed_scene()
    res = client.get("/api/scenes")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_scene_by_id():
    scene = seed_scene()
    res = client.get(f"/api/scenes/{scene['id']}")
    assert res.status_code == 200
    assert res.json()["title"] == "Test Scene"


def test_get_scene_not_found():
    res = client.get("/api/scenes/99999")
    assert res.status_code == 404


def test_update_scene():
    scene = seed_scene()
    res = client.put(f"/api/scenes/{scene['id']}", json={
        "title": "Updated", "type": "Soft", "status": "Ready",
        "description": "new desc", "session_id": None,
        "location": ["East Gate"], "cast": ["Dan"], "clock": [],
        "cuttable": False, "purpose": "", "pc_pressure": "",
        "entry_pressure": "", "exit_condition": "", "core_clue": "",
        "superior_clue": "", "optional_clue": "", "false_lead": "",
        "opening_image": "", "sensory_words": "", "interactable_objects": "",
        "rules_likely": "", "foundry_needs": "", "replacement_route": "",
        "if_succeed": "", "if_fail": "", "if_ignore": "", "if_short": "",
        "notes": "", "pinned_material": [],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Updated"
    assert data["status"] == "Ready"
    assert data["location"] == ["East Gate"]


def test_update_scene_not_found():
    res = client.put("/api/scenes/99999", json={
        "title": "X", "type": "Hard", "status": "Draft", "description": "",
        "session_id": None, "location": [], "cast": [], "clock": [],
        "cuttable": False, "purpose": "", "pc_pressure": "", "entry_pressure": "",
        "exit_condition": "", "core_clue": "", "superior_clue": "",
        "optional_clue": "", "false_lead": "", "opening_image": "",
        "sensory_words": "", "interactable_objects": "", "rules_likely": "",
        "foundry_needs": "", "replacement_route": "", "if_succeed": "",
        "if_fail": "", "if_ignore": "", "if_short": "", "notes": "",
        "pinned_material": [],
    })
    assert res.status_code == 404


def test_patch_session():
    session = seed_session()
    scene = seed_scene()
    res = client.patch(f"/api/scenes/{scene['id']}/session",
                       json={"session_id": session["id"]})
    assert res.status_code == 200
    assert res.json()["session_id"] == session["id"]


def test_patch_session_to_backlog():
    session = seed_session()
    scene = seed_scene({"session_id": session["id"]})
    res = client.patch(f"/api/scenes/{scene['id']}/session", json={"session_id": None})
    assert res.status_code == 200
    assert res.json()["session_id"] is None


def test_delete_scene():
    scene = seed_scene()
    res = client.delete(f"/api/scenes/{scene['id']}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True
    assert client.get(f"/api/scenes/{scene['id']}").status_code == 404


def test_delete_scene_not_found():
    res = client.delete("/api/scenes/99999")
    assert res.status_code == 404


def test_create_scene_invalid_status():
    res = client.post("/api/scenes", json={"title": "X", "status": "Bogus"})
    assert res.status_code == 422


def test_create_scene_invalid_type():
    res = client.post("/api/scenes", json={"title": "X", "type": "Bogus"})
    assert res.status_code == 422
