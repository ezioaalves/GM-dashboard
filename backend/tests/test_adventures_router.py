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


def test_patch_adventure_rejects_invalid_visibility():
    create = client.post("/api/adventures", json={"title": "Bad Visibility"}).json()
    res = client.patch(f"/api/adventures/{create['id']}", json={"visibility": "bogus"})
    assert res.status_code == 422


def test_patch_adventure_rejects_invalid_freshness_state():
    create = client.post("/api/adventures", json={"title": "Bad Freshness"}).json()
    res = client.patch(f"/api/adventures/{create['id']}", json={"freshness_state": "bogus"})
    assert res.status_code == 422


def test_patch_adventure_rejects_invalid_review_status():
    create = client.post("/api/adventures", json={"title": "Bad Review"}).json()
    res = client.patch(f"/api/adventures/{create['id']}", json={"review_status": "bogus"})
    assert res.status_code == 422


def test_list_adventures_filters_by_status():
    draft = client.post("/api/adventures", json={"title": "Draft One"}).json()
    ready = client.post("/api/adventures", json={"title": "Ready One"}).json()
    client.patch(f"/api/adventures/{ready['id']}", json={"status": "ready"})

    res = client.get("/api/adventures", params={"status": "ready"})
    assert res.status_code == 200
    ids = [a["id"] for a in res.json()]
    assert ready["id"] in ids
    assert draft["id"] not in ids


def test_list_adventures_rejects_invalid_status():
    res = client.get("/api/adventures", params={"status": "bogus"})
    assert res.status_code == 422


def test_list_adventures_returns_summary_fields_only():
    create = client.post("/api/adventures", json={
        "title": "Trimmed Shape Test",
        "mode": "investigation",
        "current_arc": "Training Arc",
        "pitch": "A pitch line",
    }).json()
    client.patch(f"/api/adventures/{create['id']}", json={
        "stakes": {"immediate": "Something is at risk"},
        "clue_map": {"question": "Who did it?"},
    })

    res = client.get("/api/adventures")
    assert res.status_code == 200
    item = next(a for a in res.json() if a["id"] == create["id"])
    assert item == {
        "id": create["id"],
        "graph_endpoint_id": item["graph_endpoint_id"],
        "title": "Trimmed Shape Test",
        "status": "draft",
        "mode": "investigation",
        "current_arc": "Training Arc",
        "pitch": "A pitch line",
        "session_count": 0,
    }
    assert "stakes" not in item
    assert "clue_map" not in item
    assert "location" not in item
    assert "foundry_needs" not in item
    assert "rules_notes" not in item
    assert "spine" not in item


def test_list_adventures_session_count_single_query():
    adventure = client.post("/api/adventures", json={"title": "Session Count Test"}).json()
    session_one = seed_session(number=10, name="Session A")
    session_two = seed_session(number=11, name="Session B")
    client.post(f"/api/adventures/{adventure['id']}/sessions/{session_one['id']}")
    client.post(f"/api/adventures/{adventure['id']}/sessions/{session_two['id']}")

    res = client.get("/api/adventures")
    assert res.status_code == 200
    item = next(a for a in res.json() if a["id"] == adventure["id"])
    assert item["session_count"] == 2


def test_cast_crud():
    adventure = client.post("/api/adventures", json={"title": "Cast Test"}).json()
    npc = seed_npc()

    res = client.post(f"/api/adventures/{adventure['id']}/cast", json={
        "npc_id": npc["id"], "role": "Informant", "wants_now": "Coin",
        "hides": "A debt to the clan", "if_helped": "Shares the ledger",
        "if_crossed": "Sells the PCs out",
    })
    assert res.status_code == 201
    cast_row = res.json()
    assert cast_row["npc_id"] == npc["id"]

    res = client.patch(
        f"/api/adventures/{adventure['id']}/cast/{cast_row['id']}",
        json={"role": "Double Agent"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "Double Agent"

    detail = client.get(f"/api/adventures/{adventure['id']}").json()
    assert len(detail["cast"]) == 1

    res = client.delete(f"/api/adventures/{adventure['id']}/cast/{cast_row['id']}")
    assert res.status_code == 200
    detail = client.get(f"/api/adventures/{adventure['id']}").json()
    assert detail["cast"] == []


def test_rewards_crud():
    adventure = client.post("/api/adventures", json={"title": "Rewards Test"}).json()
    res = client.post(f"/api/adventures/{adventure['id']}/rewards", json={
        "name": "Archive Access", "type": "access", "who_cares": "The 13th Tanto",
    })
    assert res.status_code == 201
    reward = res.json()
    res = client.patch(f"/api/adventures/{adventure['id']}/rewards/{reward['id']}", json={"future_hook": "Opens Room 6C"})
    assert res.status_code == 200
    assert res.json()["future_hook"] == "Opens Room 6C"
    res = client.delete(f"/api/adventures/{adventure['id']}/rewards/{reward['id']}")
    assert res.status_code == 200


def test_encounters_crud():
    adventure = client.post("/api/adventures", json={"title": "Encounters Test"}).json()
    res = client.post(f"/api/adventures/{adventure['id']}/encounters", json={
        "name": "Warehouse Ambush", "objective": "Daring Escape", "opposition": "3 genin",
    })
    assert res.status_code == 201
    encounter = res.json()
    res = client.patch(f"/api/adventures/{adventure['id']}/encounters/{encounter['id']}", json={"what_changes": "Alarm is raised"})
    assert res.status_code == 200
    res = client.delete(f"/api/adventures/{adventure['id']}/encounters/{encounter['id']}")
    assert res.status_code == 200


def test_pc_pressure_crud():
    adventure = client.post("/api/adventures", json={"title": "PC Pressure Test"}).json()
    pc = seed_pc()
    res = client.post(f"/api/adventures/{adventure['id']}/pc-pressure", json={
        "pc_id": pc["id"], "pressure": "Clan expects a clean win",
    })
    assert res.status_code == 201
    row = res.json()
    res = client.patch(f"/api/adventures/{adventure['id']}/pc-pressure/{row['id']}", json={"cost": "Public reprimand"})
    assert res.status_code == 200
    res = client.delete(f"/api/adventures/{adventure['id']}/pc-pressure/{row['id']}")
    assert res.status_code == 200


def test_clock_links_crud_requires_clock_or_thread():
    adventure = client.post("/api/adventures", json={"title": "Clock Links Test"}).json()
    res = client.post(f"/api/adventures/{adventure['id']}/clock-links", json={
        "how_it_appears": "Rumors of a raid",
    })
    assert res.status_code == 422

    thread_row_id = "thread-test-1"
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO threads (id, title, status) VALUES (%s, %s, %s)",
            (thread_row_id, "Test Thread", "active"),
        )
    conn.close()

    res = client.post(f"/api/adventures/{adventure['id']}/clock-links", json={
        "thread_id": thread_row_id, "how_it_appears": "Rumors of a raid",
    })
    assert res.status_code == 201
    link = res.json()
    assert link["thread_id"] == thread_row_id

    res = client.delete(f"/api/adventures/{adventure['id']}/clock-links/{link['id']}")
    assert res.status_code == 200


def seed_session(number=1, name="Test Session"):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO sessions (number, name, status) VALUES (%s, %s, %s) RETURNING id, number, name",
            (number, name, "planned"),
        )
        row = dict(cur.fetchone())
    conn.close()
    return row


def test_link_and_unlink_session():
    adventure = client.post("/api/adventures", json={"title": "Linked Adventure"}).json()
    session = seed_session()

    res = client.post(f"/api/adventures/{adventure['id']}/sessions/{session['id']}")
    assert res.status_code == 200
    detail = client.get(f"/api/adventures/{adventure['id']}").json()
    assert detail["sessions"] == [{"id": session["id"], "title": session["name"]}]

    res = client.get(f"/api/sessions/{session['id']}")
    assert res.status_code == 200
    assert res.json()["adventures"] == [{"id": adventure["id"], "title": adventure["title"]}]

    res = client.delete(f"/api/adventures/{adventure['id']}/sessions/{session['id']}")
    assert res.status_code == 200
    detail = client.get(f"/api/adventures/{adventure['id']}").json()
    assert detail["sessions"] == []


def test_link_session_many_to_many():
    adventure_a = client.post("/api/adventures", json={"title": "Adventure A"}).json()
    adventure_b = client.post("/api/adventures", json={"title": "Adventure B"}).json()
    session = seed_session(number=2, name="Shared Session")

    client.post(f"/api/adventures/{adventure_a['id']}/sessions/{session['id']}")
    client.post(f"/api/adventures/{adventure_b['id']}/sessions/{session['id']}")

    res = client.get(f"/api/sessions/{session['id']}")
    titles = {a["title"] for a in res.json()["adventures"]}
    assert titles == {"Adventure A", "Adventure B"}


def test_apply_six_beat_spine_preset():
    adventure = client.post("/api/adventures", json={"title": "Spine Test"}).json()
    res = client.post(f"/api/adventures/{adventure['id']}/apply-spine-preset", json={"preset": "six_beat"})
    assert res.status_code == 200
    labels = [beat["label"] for beat in res.json()["spine"]]
    assert labels == [
        "Inciting incident", "First pressure", "Complication",
        "Revelation", "Climax", "Consequence",
    ]
    assert all(beat["text"] == "" for beat in res.json()["spine"])


def test_apply_five_room_spine_preset():
    adventure = client.post("/api/adventures", json={"title": "Dungeon Test"}).json()
    res = client.post(f"/api/adventures/{adventure['id']}/apply-spine-preset", json={"preset": "five_room"})
    assert res.status_code == 200
    labels = [beat["label"] for beat in res.json()["spine"]]
    assert labels == [
        "Entrance and Guardian", "Puzzle or Roleplaying Challenge", "Trick or Setback",
        "Climax, Big Battle or Conflict", "Reward, Revelation, Plot Twist",
    ]


def test_apply_spine_preset_invalid_name():
    adventure = client.post("/api/adventures", json={"title": "Bad Preset"}).json()
    res = client.post(f"/api/adventures/{adventure['id']}/apply-spine-preset", json={"preset": "nonsense"})
    assert res.status_code == 422
