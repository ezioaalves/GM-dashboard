from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from gm_dashboard import scenes_router
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
        cur.execute("DELETE FROM scenes")
        cur.execute("DELETE FROM lore_assets")
    conn.close()


@pytest.fixture(autouse=True)
def clean_tables():
    _clean()
    yield
    _clean()


class FakeExportRelay:
    def __init__(self):
        self.journals: dict[str, str] = {}
        self.fail = False

    def execute_js(self, script: str) -> dict:
        if self.fail:
            return {"ok": False, "error": "relay down"}
        if "JournalEntry.implementation.create" in script:
            uuid = "JournalEntry.new1"
            self.journals[uuid] = script
            return {"ok": True, "uuid": uuid}
        for uuid in self.journals:
            if uuid in script:
                self.journals[uuid] = script
                return {"ok": True, "uuid": uuid}
        return {"ok": False, "error": "journal not found"}


@pytest.fixture
def fake_export_relay(monkeypatch):
    relay = FakeExportRelay()
    monkeypatch.setattr(scenes_router, "load_relay_client", lambda env="test": relay)
    return relay


def _seed_scene(pinned_material: list[dict]) -> int:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO scenes (title, description, pinned_material)
                VALUES ('Ambush at the Gate', 'A trap springs.', %s)
                RETURNING id
                """,
                (psycopg2.extras.Json(pinned_material),),
            )
            return cur.fetchone()["id"]
    finally:
        conn.close()


def _seed_asset(source_path: str, mirror_state: str, foundry_path: str = "") -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lore_assets (source_path, asset_type, mirror_state, foundry_path)
                VALUES (%s, 'image', %s, %s)
                """,
                (source_path, mirror_state, foundry_path),
            )
    finally:
        conn.close()


def test_export_scene_creates_journal_first_time(fake_export_relay):
    _seed_asset("Lore/Assets/Images/gate.png", "mirrored", "worlds/kaihou/assets/gate.png")
    scene_id = _seed_scene([{"path": "Lore/Assets/Images/gate.png", "title": "Gate"}])

    res = client.post(f"/api/scenes/{scene_id}/foundry/export", json={"env": "test"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exported"] is True
    assert body["foundry_journal_id"] == "JournalEntry.new1"
    assert body["skipped_unmirrored"] == []

    scene = client.get(f"/api/scenes/{scene_id}").json()
    assert scene["foundry_journal_id"] == "JournalEntry.new1"
    assert scene["foundry_export_status"] == "exported"


def test_export_scene_skips_unmirrored_assets(fake_export_relay):
    _seed_asset("Lore/Assets/Images/unmirrored.png", "not_mirrored")
    scene_id = _seed_scene([{"path": "Lore/Assets/Images/unmirrored.png", "title": "Unmirrored"}])

    res = client.post(f"/api/scenes/{scene_id}/foundry/export", json={"env": "test"})
    assert res.status_code == 200, res.text
    assert res.json()["skipped_unmirrored"] == ["Lore/Assets/Images/unmirrored.png"]


def test_export_scene_second_time_updates_existing_journal(fake_export_relay):
    scene_id = _seed_scene([])
    first = client.post(f"/api/scenes/{scene_id}/foundry/export", json={"env": "test"})
    assert first.status_code == 200

    second = client.post(f"/api/scenes/{scene_id}/foundry/export", json={"env": "test"})
    assert second.status_code == 200
    assert second.json()["foundry_journal_id"] == first.json()["foundry_journal_id"]
    assert len(fake_export_relay.journals) == 1


def test_export_scene_relay_failure_sets_failed_status(fake_export_relay):
    fake_export_relay.fail = True
    scene_id = _seed_scene([])

    res = client.post(f"/api/scenes/{scene_id}/foundry/export", json={"env": "test"})
    assert res.status_code == 502

    scene = client.get(f"/api/scenes/{scene_id}").json()
    assert scene["foundry_export_status"] == "failed"


def test_export_missing_scene_returns_404(fake_export_relay):
    res = client.post("/api/scenes/999999/foundry/export", json={"env": "test"})
    assert res.status_code == 404
