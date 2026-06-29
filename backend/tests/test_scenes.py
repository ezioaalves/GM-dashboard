from __future__ import annotations

import os
import pytest
import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from gm_dashboard.api import app

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm"
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tables():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM scenes")
        cur.execute("DELETE FROM session_notes")
        cur.execute("DELETE FROM sessions")
    conn.close()
    yield
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM scenes")
        cur.execute("DELETE FROM session_notes")
        cur.execute("DELETE FROM sessions")
    conn.close()


def seed_session(number=1, name="Test Session"):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO sessions (number, name, status, date, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, number, name, status, date, notes
            """,
            (number, name, "Planned", None, ""),
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
    res = client.post("/api/sessions", json={
        "number": 18,
        "name": "The Iron Keep",
        "status": "Active",
        "date": "2026-06-27",
        "notes": "Open at the keep gates.",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["number"] == 18
    assert data["name"] == "The Iron Keep"
    assert data["status"] == "Active"
    assert data["date"] == "2026-06-27"
    assert data["notes"] == "Open at the keep gates."
    assert data["scene_count"] == 0
    assert "id" in data


def test_list_sessions_returns_created():
    seed_session(number=17, name="Old session")
    session = seed_session(number=18, name="New session")
    seed_scene({"session_id": session["id"]})
    res = client.get("/api/sessions")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    # Ordered by number DESC
    assert data[0]["number"] == 18
    assert data[0]["status"] == "Planned"
    assert data[0]["date"] is None
    assert data[0]["notes"] == ""
    assert data[0]["scene_count"] == 1


def test_create_session_duplicate_number():
    seed_session(number=18)
    res = client.post("/api/sessions", json={"number": 18, "name": "Duplicate"})
    assert res.status_code == 409


def test_create_session_invalid_status():
    res = client.post("/api/sessions", json={"number": 18, "status": "Bogus"})
    assert res.status_code == 422


def test_update_session():
    session = seed_session(number=18)
    seed_scene({"session_id": session["id"]})
    res = client.put(f"/api/sessions/{session['id']}", json={
        "number": 19,
        "name": "Updated Session",
        "status": "Played",
        "date": "2026-06-28",
        "notes": "Wrapped the council scene.",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["number"] == 19
    assert data["name"] == "Updated Session"
    assert data["status"] == "Played"
    assert data["date"] == "2026-06-28"
    assert data["notes"] == "Wrapped the council scene."
    assert data["scene_count"] == 1


def test_update_session_not_found():
    res = client.put("/api/sessions/99999", json={
        "number": 19,
        "name": "Missing",
        "status": "Planned",
        "date": None,
        "notes": "",
    })
    assert res.status_code == 404


def test_update_session_duplicate_number():
    seed_session(number=18)
    session = seed_session(number=19)
    res = client.put(f"/api/sessions/{session['id']}", json={
        "number": 18,
        "name": "Duplicate",
        "status": "Planned",
        "date": None,
        "notes": "",
    })
    assert res.status_code == 409


def test_delete_session_moves_scenes_to_backlog():
    session = seed_session()
    scene = seed_scene({"session_id": session["id"]})
    res = client.delete(f"/api/sessions/{session['id']}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True
    scene_res = client.get(f"/api/scenes/{scene['id']}")
    assert scene_res.status_code == 200
    assert scene_res.json()["session_id"] is None


def test_delete_session_not_found():
    res = client.delete("/api/sessions/99999")
    assert res.status_code == 404


def test_patch_session_status():
    session = seed_session(number=18, name="Test Session")
    res = client.patch(f"/api/sessions/{session['id']}/status", json={"status": "Active"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == session["id"]
    assert data["status"] == "Active"

    # Verify status was updated
    res = client.get("/api/sessions")
    assert res.json()[0]["status"] == "Active"


def test_patch_session_status_invalid():
    session = seed_session()
    res = client.patch(f"/api/sessions/{session['id']}/status", json={"status": "Invalid"})
    assert res.status_code == 422


def test_patch_session_status_not_found():
    res = client.patch("/api/sessions/99999/status", json={"status": "Played"})
    assert res.status_code == 404


def test_get_session_note_empty():
    session = seed_session()
    res = client.get(f"/api/sessions/{session['id']}/note")
    assert res.status_code == 200
    assert res.json() is None


def test_upsert_session_note():
    session = seed_session()
    payload = {
        "scenes": ["Council opens", "Dan presses the clue"],
        "npcs_present": ["Dan"],
        "clues_discovered": ["The seal is forged"],
        "threads_touched": ["iron-keep"],
        "unresolved_questions": ["Who forged it?"],
        "next_session_hook": "Alarm bells ring",
        "memory": "Strong table energy.",
        "markdown": "# Custom",
        "target_path": "Campaign Management/session-logs/01-custom.md",
        "status": "draft",
    }
    res = client.put(f"/api/sessions/{session['id']}/note", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session["id"]
    assert data["scenes"] == ["Council opens", "Dan presses the clue"]
    assert data["npcs_present"] == ["Dan"]
    assert data["markdown"] == "# Custom"

    res = client.get(f"/api/sessions/{session['id']}/note")
    assert res.status_code == 200
    assert res.json()["next_session_hook"] == "Alarm bells ring"


def test_generate_session_note_persists_markdown():
    session = seed_session(number=18, name="The Iron Keep")
    res = client.post(f"/api/sessions/{session['id']}/note/generate", json={
        "scenes": ["The party enters the keep"],
        "npcs_present": ["Dattoumaru"],
        "clues_discovered": ["The ledger is altered"],
        "threads_touched": ["iron-keep"],
        "unresolved_questions": ["Where is the real ledger?"],
        "next_session_hook": "The patrol arrives",
        "memory": "Keep the pressure on.",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["target_path"] == "Campaign Management/session-logs/18-the-iron-keep.md"
    assert "# Session 18 - The Iron Keep" in data["markdown"]
    assert "1. The party enters the keep" in data["markdown"]
    assert "- Dattoumaru" in data["markdown"]


def test_session_note_deleted_with_session():
    session = seed_session()
    client.put(f"/api/sessions/{session['id']}/note", json={"memory": "Stored note"})
    assert client.get(f"/api/sessions/{session['id']}/note").json()["memory"] == "Stored note"
    assert client.delete(f"/api/sessions/{session['id']}").status_code == 200
    assert client.get(f"/api/sessions/{session['id']}/note").status_code == 404


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
        "session_id": session["id"], "placement": "floating", "sort_order": 2,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["session_id"] == session["id"]
    assert data["placement"] == "floating"
    assert data["sort_order"] == 2


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
                       json={"session_id": session["id"], "placement": "ordered", "sort_order": 4})
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session["id"]
    assert data["placement"] == "ordered"
    assert data["sort_order"] == 4


def test_patch_session_to_backlog():
    session = seed_session()
    scene = seed_scene({"session_id": session["id"]})
    res = client.patch(f"/api/scenes/{scene['id']}/session", json={"session_id": None})
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] is None
    assert data["placement"] == "backlog"


def test_session_detail_groups_scene_placements_and_scene_order_replaces_assignments():
    session = seed_session(number=20, name="Placement Test")
    ordered = seed_scene({"title": "Opening", "session_id": session["id"]})
    floating = seed_scene({"title": "Optional clue", "session_id": session["id"]})
    backlog = seed_scene({"title": "Backlog pressure", "session_id": None})
    removed = seed_scene({"title": "Removed scene", "session_id": session["id"]})

    res = client.post(
        f"/api/sessions/{session['id']}/scene-order",
        json={
            "ordered_scene_ids": [ordered["id"]],
            "floating_scene_ids": [floating["id"]],
            "backlog_scene_ids": [backlog["id"]],
        },
    )
    assert res.status_code == 200
    detail = res.json()
    assert [scene["id"] for scene in detail["scenes"]["ordered"]] == [ordered["id"]]
    assert [scene["id"] for scene in detail["scenes"]["floating"]] == [floating["id"]]
    assert detail["scenes"]["backlog"] == []

    assert client.get(f"/api/scenes/{backlog['id']}").json()["session_id"] is None
    removed_scene = client.get(f"/api/scenes/{removed['id']}").json()
    assert removed_scene["session_id"] is None
    assert removed_scene["placement"] == "backlog"

    detail_res = client.get(f"/api/sessions/{session['id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["scenes"]["ordered"][0]["title"] == "Opening"


def test_session_scene_order_rejects_duplicate_scene_ids():
    session = seed_session()
    scene = seed_scene()
    res = client.post(
        f"/api/sessions/{session['id']}/scene-order",
        json={
            "ordered_scene_ids": [scene["id"]],
            "floating_scene_ids": [scene["id"]],
            "backlog_scene_ids": [],
        },
    )
    assert res.status_code == 422


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


def test_list_scenes_filtered_by_session_id():
    session_a = seed_session(number=1, name="Session A")
    session_b = seed_session(number=2, name="Session B")
    seed_scene({"title": "Scene in A", "session_id": session_a["id"]})
    seed_scene({"title": "Scene in B", "session_id": session_b["id"]})
    seed_scene({"title": "Scene in backlog", "session_id": None})

    res = client.get(f"/api/scenes?session_id={session_a['id']}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["title"] == "Scene in A"
    assert data[0]["session_id"] == session_a["id"]


def test_list_scenes_unfiltered_returns_all():
    session = seed_session()
    seed_scene({"title": "Scene with session", "session_id": session["id"]})
    seed_scene({"title": "Scene in backlog", "session_id": None})

    res = client.get("/api/scenes")
    assert res.status_code == 200
    assert len(res.json()) == 2
