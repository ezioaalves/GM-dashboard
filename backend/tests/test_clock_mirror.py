from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from gm_dashboard.api import app
from gm_dashboard import clockworks_mirror
from gm_dashboard.relay_client import RelayClient, RelayError

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
        cur.execute("DELETE FROM clock_ticks")
        cur.execute("DELETE FROM cascade_rules")
        cur.execute("DELETE FROM lore_relationships")
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
        cur.execute("DELETE FROM clocks")
    conn.close()


@pytest.fixture
def clean_db():
    _clean()
    yield
    _clean()


class FakeRelay:
    setting_uuid = "Setting.clockList"

    def __init__(self):
        self.clock_list: dict[str, dict] = {}

    def search(self, query: str) -> list[dict]:
        return [{"uuid": self.setting_uuid, "documentType": "Setting"}]

    def get(self, uuid: str) -> dict:
        assert uuid == self.setting_uuid
        return {"key": clockworks_mirror.SETTING_KEY, "value": json.dumps(self.clock_list)}

    def update(self, uuid: str, data: dict) -> dict:
        assert uuid == self.setting_uuid
        self.clock_list = json.loads(data["value"])
        return {"ok": True}


@pytest.fixture
def fake_relay(monkeypatch):
    relay = FakeRelay()
    monkeypatch.setattr(clockworks_mirror, "load_relay_client", lambda env="test": relay)
    return relay


def _insert_clock(name="Mirror Clock", kind="progress", segments=6, filled=2) -> str:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO clocks (name, kind, segments, filled)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (name, kind, segments, filled),
            )
            return str(cur.fetchone()["id"])
    finally:
        conn.close()


def _clock(clock_id: str) -> dict:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM clocks WHERE id = %s", (clock_id,))
            return dict(cur.fetchone())
    finally:
        conn.close()


def _accept(review_id: str) -> None:
    res = client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    assert res.status_code == 200, res.text


def _apply(review_id: str) -> dict:
    res = client.post(f"/api/sync/reviews/{review_id}/apply", json={"confirmation": True})
    assert res.status_code == 200, res.text
    return res.json()


class TestRelayClient:
    def _client(self):
        return RelayClient("https://relay.example", "key123", "client-abc")

    @patch("gm_dashboard.relay_client.requests.get")
    def test_get_unwraps_data(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"type": "get", "uuid": "Setting.x", "data": {"key": "v"}},
        )
        assert self._client().get("Setting.x") == {"key": "v"}
        args, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"x-api-key": "key123"}
        assert kwargs["params"] == {"uuid": "Setting.x", "clientId": "client-abc"}

    @patch("gm_dashboard.relay_client.requests.put")
    def test_update_wraps_payload(self, mock_put):
        mock_put.return_value = MagicMock(
            status_code=200, json=lambda: {"entity": [{"ok": True}]}
        )
        out = self._client().update("Setting.x", {"value": "{}"})
        assert out == {"entity": [{"ok": True}]}
        assert mock_put.call_args.kwargs["json"] == {"data": {"value": "{}"}}

    @patch("gm_dashboard.relay_client.requests.get")
    def test_error_raises_relay_error(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=404, json=lambda: {"error": "nf", "message": "not found"},
            text="not found",
        )
        with pytest.raises(RelayError):
            self._client().get("Setting.missing")


class TestClockWorksMirror:
    def test_render_clockworks_entry(self):
        progress = {"name": "Progress", "segments": 6, "filled": 2}
        assert clockworks_mirror.render_clockworks_entry(progress, "cw-a") == {
            "id": "cw-a",
            "name": "Progress",
            "max": 6,
            "value": 2,
            "listPosition": 0,
            "persist": True,
        }
        countdown = {"name": "Countdown", "segments": 6, "filled": 4}
        assert clockworks_mirror.render_clockworks_entry(countdown, "cw-b")["value"] == 4

    def test_mirror_review_flow(self, clean_db, fake_relay):
        clock_id = _insert_clock()
        created = client.post(f"/api/clocks/{clock_id}/mirror", json={"env": "test"})
        assert created.status_code == 200, created.text
        review_id = created.json()["id"]
        _accept(review_id)

        applied = _apply(review_id)
        foundry_id = applied["foundry_clock_id"]
        assert fake_relay.clock_list[foundry_id]["name"] == "Mirror Clock"
        assert fake_relay.clock_list[foundry_id]["max"] == 6
        assert fake_relay.clock_list[foundry_id]["value"] == 2

        clock = _clock(clock_id)
        assert clock["foundry_clock_id_test"] == foundry_id
        assert clock["mirror_state"] == "mirrored"
        assert clock["last_mirrored_at"] is not None

        conn = _connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT status FROM sync_jobs WHERE review_id = %s", (review_id,))
                assert cur.fetchone()["status"] == "succeeded"
        finally:
            conn.close()

    def test_mirror_second_env_needs_new_review(self, clean_db, fake_relay):
        clock_id = _insert_clock()
        first = client.post(f"/api/clocks/{clock_id}/mirror", json={"env": "test"})
        assert first.status_code == 200, first.text
        _accept(first.json()["id"])
        _apply(first.json()["id"])

        duplicate = client.post(f"/api/clocks/{clock_id}/mirror", json={"env": "test"})
        assert duplicate.status_code == 409

        second = client.post(f"/api/clocks/{clock_id}/mirror", json={"env": "prod"})
        assert second.status_code == 200, second.text
        _accept(second.json()["id"])
        _apply(second.json()["id"])
        clock = _clock(clock_id)
        assert clock["foundry_clock_id_test"]
        assert clock["foundry_clock_id_prod"]

    def test_unmirror_review(self, clean_db, fake_relay):
        clock_id = _insert_clock()
        mirror = client.post(f"/api/clocks/{clock_id}/mirror", json={"env": "test"})
        _accept(mirror.json()["id"])
        applied = _apply(mirror.json()["id"])
        foundry_id = applied["foundry_clock_id"]

        unmirror = client.post(
            f"/api/clocks/{clock_id}/mirror",
            json={"env": "test", "action": "unmirror"},
        )
        assert unmirror.status_code == 200, unmirror.text
        _accept(unmirror.json()["id"])
        _apply(unmirror.json()["id"])

        assert foundry_id not in fake_relay.clock_list
        clock = _clock(clock_id)
        assert clock["foundry_clock_id_test"] == ""
        assert clock["mirror_state"] == "not_mirrored"

    def test_drift_detection_and_adopt(self, clean_db, fake_relay):
        clock_id = _insert_clock(filled=2)
        mirror = client.post(f"/api/clocks/{clock_id}/mirror", json={"env": "test"})
        _accept(mirror.json()["id"])
        applied = _apply(mirror.json()["id"])
        foundry_id = applied["foundry_clock_id"]
        fake_relay.clock_list[foundry_id]["value"] = 4

        drift = client.get("/api/clocks/mirror/drift?env=test")
        assert drift.status_code == 200, drift.text
        verdict = drift.json()["verdicts"][0]
        assert verdict == {
            "clock_id": clock_id,
            "kind": "value_drift",
            "fields": {"value": {"engine": 2, "foundry": 4}},
        }
        assert _clock(clock_id)["freshness_state"] == "stale_mirror"

        adopt = client.post(
            f"/api/clocks/{clock_id}/mirror/adopt",
            json={"env": "test", "reason": "Adopt smoke", "foundry_value": 4},
        )
        assert adopt.status_code == 200, adopt.text
        _accept(adopt.json()["id"])
        _apply(adopt.json()["id"])

        clock = _clock(clock_id)
        assert clock["filled"] == 4
        assert clock["freshness_state"] == "fresh"
        conn = _connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT delta, reason, caused_by FROM clock_ticks WHERE clock_id = %s",
                    (clock_id,),
                )
                tick = dict(cur.fetchone())
                assert tick == {"delta": 2, "reason": "Adopt smoke", "caused_by": "drift_adopt"}
        finally:
            conn.close()

    def test_drift_missing_mirror(self, clean_db, fake_relay):
        clock_id = _insert_clock()
        mirror = client.post(f"/api/clocks/{clock_id}/mirror", json={"env": "test"})
        _accept(mirror.json()["id"])
        applied = _apply(mirror.json()["id"])
        del fake_relay.clock_list[applied["foundry_clock_id"]]

        drift = client.get("/api/clocks/mirror/drift?env=test")
        assert drift.status_code == 200, drift.text
        assert drift.json()["verdicts"] == [{"clock_id": clock_id, "kind": "missing_mirror"}]
        assert _clock(clock_id)["mirror_state"] == "missing_mirror"
