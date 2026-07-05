from __future__ import annotations

import os
import pathlib
import subprocess

import psycopg2
import psycopg2.extras
import pytest
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


def _clean() -> None:
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM clock_ticks")
        cur.execute("DELETE FROM cascade_rules")
        cur.execute("DELETE FROM lore_relationships")
        cur.execute("DELETE FROM clocks")
        cur.execute("DELETE FROM threads")
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
    conn.close()


@pytest.fixture(autouse=True)
def clean_tables():
    _clean()
    yield
    _clean()


def _insert_clock(name="Test Clock", kind="progress", segments=6, filled=0, **extra):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cols = {"name": name, "kind": kind, "segments": segments, "filled": filled, **extra}
        keys = ", ".join(cols)
        vals = ", ".join(f"%({k})s" for k in cols)
        cur.execute(
            f"INSERT INTO clocks ({keys}) VALUES ({vals}) RETURNING id, graph_endpoint_id",
            cols,
        )
        row = dict(cur.fetchone())
    conn.close()
    return row


class TestSchema:
    def test_clock_graph_endpoint_id_trigger(self):
        row = _insert_clock()
        assert row["graph_endpoint_id"] == f"clock:{row['id']}"

    def test_filled_bounded_by_segments(self):
        with pytest.raises(psycopg2.errors.CheckViolation):
            _insert_clock(filled=7, segments=6)

    def test_kind_constrained(self):
        with pytest.raises(psycopg2.errors.CheckViolation):
            _insert_clock(kind="timer")

    def test_tick_reason_must_be_non_empty(self):
        clock = _insert_clock()
        conn = _connect()
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.CheckViolation):
                cur.execute(
                    """
                    INSERT INTO clock_ticks (clock_id, delta, filled_before, filled_after,
                                             reason, caused_by, trigger_fire_id)
                    VALUES (%s, 1, 0, 1, '', 'manual', gen_random_uuid())
                    """,
                    (clock["id"],),
                )
        conn.close()

    def test_pcs_have_graph_endpoint_id_column(self):
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'pcs' AND column_name = 'graph_endpoint_id'
                """
            )
            assert cur.fetchone() is not None
        conn.close()


APP_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _alembic(*args: str) -> None:
    subprocess.run(
        ["alembic", *args],
        cwd=APP_ROOT,
        env={**os.environ, "DATABASE_URL": DATABASE_URL},
        check=True,
        capture_output=True,
    )


class TestThreadClockDataMigration:
    def test_migration_016_migrates_thread_inline_clocks(self):
        conn = _connect()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO threads (id, title, status, clock_label, clock_value, clock_max)
                VALUES ('thr-mig-test', 'Migration Test Thread', 'active',
                        'Migration Test Clock', 99, 6)
                RETURNING graph_endpoint_id
                """
            )
            thread_gid = cur.fetchone()["graph_endpoint_id"]
        conn.close()

        # Replay migration 016 against the seeded thread so the data-migration
        # path (including INSERT INTO lore_relationships with source_type='clock')
        # actually executes.
        _alembic("downgrade", "015")
        _alembic("upgrade", "head")

        conn = _connect()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT graph_endpoint_id, name, kind, segments, filled, origin, lifecycle
                FROM clocks WHERE origin = 'thread_migration'
                """
            )
            clocks = [dict(r) for r in cur.fetchall()]
            assert len(clocks) == 1
            clock = clocks[0]
            assert clock["name"] == "Migration Test Clock"
            assert clock["kind"] == "progress"
            assert clock["segments"] == 6
            assert clock["filled"] == 6  # clock_value 99 clamped to clock_max
            assert clock["lifecycle"] == "active"

            cur.execute(
                """
                SELECT source_type, source_id, target_type, target_id,
                       relationship_type, direction, provenance, review_status
                FROM lore_relationships WHERE source_type = 'clock'
                """
            )
            rels = [dict(r) for r in cur.fetchall()]
            assert len(rels) == 1
            rel = rels[0]
            assert rel["source_id"] == clock["graph_endpoint_id"]
            assert rel["target_type"] == "thread"
            assert rel["target_id"] == thread_gid
            assert rel["relationship_type"] == "tracks"
            assert rel["direction"] == "directed"
            assert rel["provenance"] == "system"
            assert rel["review_status"] == "accepted"
        conn.close()


import uuid as uuid_mod

from gm_dashboard.clock_engine import EngineError, fire_manual_tick, fire_rule


def _insert_rule(effects, name=None, trigger_kind="manual", trigger_clock_id=None,
                 trigger_event=None, condition=None, enabled=True, title="Rule"):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO cascade_rules
              (name, title, trigger_kind, trigger_clock_id, trigger_event,
               condition, effects, enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                name or f"rule-{uuid_mod.uuid4().hex[:8]}", title, trigger_kind,
                trigger_clock_id, trigger_event,
                psycopg2.extras.Json(condition or {}),
                psycopg2.extras.Json(effects), enabled,
            ),
        )
        rid = str(cur.fetchone()["id"])
    conn.close()
    return rid


def _clock_row(clock_id):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM clocks WHERE id = %s", (clock_id,))
        row = dict(cur.fetchone())
    conn.close()
    return row


def _ticks(clock_id):
    conn = _connect()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM clock_ticks WHERE clock_id = %s ORDER BY created_at", (clock_id,)
        )
        rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


class TestEngineDB:
    def test_manual_tick_writes_ledger_and_state(self):
        cid = _insert_clock()["id"]
        conn = _connect()
        conn.autocommit = False
        result = fire_manual_tick(conn, str(cid), 2, "Lead found")
        conn.close()
        assert _clock_row(cid)["filled"] == 2
        ticks = _ticks(cid)
        assert len(ticks) == 1
        assert ticks[0]["reason"] == "Lead found"
        assert ticks[0]["caused_by"] == "manual"
        assert result["applied"][0]["filled_after"] == 2

    def test_empty_reason_rejected(self):
        cid = _insert_clock()["id"]
        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError):
            fire_manual_tick(conn, str(cid), 1, "   ")
        conn.close()

    def test_tick_on_resolved_clock_rejected(self):
        cid = _insert_clock(lifecycle="resolved")["id"]
        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError):
            fire_manual_tick(conn, str(cid), 1, "why")
        conn.close()

    def test_dry_run_writes_nothing(self):
        cid = _insert_clock()["id"]
        conn = _connect()
        conn.autocommit = False
        result = fire_manual_tick(conn, str(cid), 1, "preview", dry_run=True)
        conn.close()
        assert result["dry_run"] is True
        assert result["applied"][0]["filled_after"] == 1
        assert _clock_row(cid)["filled"] == 0
        assert _ticks(cid) == []

    def test_fire_manual_rule_moves_two_clocks_one_audit_each(self):
        corruption = _insert_clock(name="Corruption", segments=8)["id"]
        trade = _insert_clock(name="Trade Safety", segments=8, filled=4)["id"]
        rid = _insert_rule(
            effects=[
                {"clock_id": str(corruption), "delta": 1,
                 "reason_template": "Failed patrol ({trigger_note})"},
                {"clock_id": str(trade), "delta": -1,
                 "reason_template": "Failed patrol ({trigger_note})"},
            ],
            title="Failed Patrol",
        )
        conn = _connect()
        conn.autocommit = False
        result = fire_rule(conn, rid, trigger_note="session 12")
        conn.close()
        assert len(result["applied"]) == 2
        fire_ids = {t["trigger_fire_id"] for t in _ticks(corruption) + _ticks(trade)}
        assert len(fire_ids) == 1
        assert _ticks(corruption)[0]["reason"] == "Failed patrol (session 12)"
        assert _clock_row(trade)["filled"] == 3

    def test_clock_event_rule_not_directly_fireable(self):
        cid = _insert_clock()["id"]
        rid = _insert_rule(
            effects=[{"clock_id": str(cid), "delta": 1, "reason_template": "x"}],
            trigger_kind="clock_event", trigger_clock_id=str(cid), trigger_event="filled",
        )
        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError):
            fire_rule(conn, rid)
        conn.close()

    def test_chained_event_rule_fires_from_manual_tick(self):
        discovery = _insert_clock(name="Discovery", segments=2, filled=1)["id"]
        thread_clock = _insert_clock(name="Thread pressure", segments=6)["id"]
        _insert_rule(
            effects=[{"clock_id": str(thread_clock), "delta": 1,
                      "reason_template": "Discovery filled"}],
            trigger_kind="clock_event", trigger_clock_id=str(discovery),
            trigger_event="filled",
        )
        conn = _connect()
        conn.autocommit = False
        result = fire_manual_tick(conn, str(discovery), 1, "Strong lead")
        conn.close()
        assert len(result["applied"]) == 2
        assert _clock_row(thread_clock)["filled"] == 1
        chained = _ticks(thread_clock)[0]
        assert chained["hop_depth"] == 1
        assert chained["caused_by"] == "rule"

    def test_atomic_rollback_on_midcascade_error(self, monkeypatch):
        cid = _insert_clock()["id"]
        conn = _connect()
        conn.autocommit = False
        import gm_dashboard.clock_engine as ce

        real = ce._write_fire_result

        def boom(*args, **kwargs):
            raise RuntimeError("mid-write failure")

        monkeypatch.setattr(ce, "_write_fire_result", boom)
        with pytest.raises(RuntimeError):
            fire_manual_tick(conn, str(cid), 1, "will roll back")
        monkeypatch.setattr(ce, "_write_fire_result", real)
        conn.close()
        assert _clock_row(cid)["filled"] == 0
        assert _ticks(cid) == []

    def test_unknown_clock_id_rejected(self):
        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError, match="clock not found"):
            fire_manual_tick(conn, str(uuid_mod.uuid4()), 1, "why")
        conn.close()

    def test_unknown_rule_id_rejected(self):
        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError, match="cascade rule not found"):
            fire_rule(conn, str(uuid_mod.uuid4()))
        conn.close()

    def test_disabled_rule_refused(self):
        cid = _insert_clock()["id"]
        rid = _insert_rule(
            effects=[{"clock_id": str(cid), "delta": 1, "reason_template": "x"}],
            enabled=False,
        )
        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError, match="disabled"):
            fire_rule(conn, rid)
        conn.close()
        assert _ticks(cid) == []

    def test_zero_delta_rejected(self):
        cid = _insert_clock()["id"]
        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError, match="non-zero"):
            fire_manual_tick(conn, str(cid), 0, "why")
        conn.close()
        assert _ticks(cid) == []

    def test_rule_condition_evaluated_under_fire_transaction(self, monkeypatch):
        # Condition gated on a clock's fill level; assert the gate both refuses
        # and fires through fire_rule, and that evaluation happens against the
        # exact state object _load_state returned inside _run_fire's transaction.
        gate = _insert_clock(name="Gate", segments=6, filled=1)["id"]
        target = _insert_clock(name="Target", segments=6)["id"]
        rid = _insert_rule(
            effects=[{"clock_id": str(target), "delta": 1, "reason_template": "gated"}],
            condition={"clock": str(gate), "op": "gte", "value": 2},
        )

        import gm_dashboard.clock_engine as ce

        seen = {}
        real_load = ce._load_state
        real_eval = ce.evaluate_condition

        def spy_load(cur):
            state = real_load(cur)
            seen["loaded"] = state
            return state

        def spy_eval(condition, clocks):
            if condition:  # the rule's gate condition, not an empty default
                seen.setdefault("evaluated_with", clocks)
            return real_eval(condition, clocks)

        monkeypatch.setattr(ce, "_load_state", spy_load)
        monkeypatch.setattr(ce, "evaluate_condition", spy_eval)

        conn = _connect()
        conn.autocommit = False
        with pytest.raises(EngineError, match="condition is not met"):
            fire_rule(conn, rid)
        conn.close()
        assert seen["evaluated_with"] is seen["loaded"]
        assert _ticks(target) == []

        # Raise the gate; the same rule now fires.
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("UPDATE clocks SET filled = 2 WHERE id = %s", (gate,))
        conn.close()
        seen.clear()
        conn = _connect()
        conn.autocommit = False
        result = fire_rule(conn, rid)
        conn.close()
        assert len(result["applied"]) == 1
        assert seen["evaluated_with"] is seen["loaded"]
        assert _clock_row(target)["filled"] == 1


class TestClockCrud:
    def test_create_progress_starts_empty_countdown_starts_full(self):
        prog = client.post("/api/clocks", json={"name": "Discovery", "kind": "progress", "segments": 6}).json()
        count = client.post("/api/clocks", json={"name": "Recall", "kind": "countdown", "segments": 8}).json()
        assert prog["filled"] == 0
        assert count["filled"] == 8

    def test_create_validates(self):
        assert client.post("/api/clocks", json={"name": "", "kind": "progress", "segments": 6}).status_code == 422
        assert client.post("/api/clocks", json={"name": "x", "kind": "timer", "segments": 6}).status_code == 422
        assert client.post("/api/clocks", json={"name": "x", "kind": "progress", "segments": 0}).status_code == 422

    def test_list_filters_by_lifecycle_and_kind(self):
        client.post("/api/clocks", json={"name": "A", "kind": "progress", "segments": 4})
        rid = client.post("/api/clocks", json={"name": "B", "kind": "countdown", "segments": 4}).json()["id"]
        client.patch(f"/api/clocks/{rid}/lifecycle", json={"lifecycle": "resolved", "resolution": "done"})
        active = client.get("/api/clocks", params={"lifecycle": "active"}).json()
        assert [c["name"] for c in active] == ["A"]
        countdowns = client.get("/api/clocks", params={"kind": "countdown"}).json()
        assert [c["name"] for c in countdowns] == ["B"]

    def test_patch_segments_reclamps_filled(self):
        cid = client.post("/api/clocks", json={"name": "C", "kind": "progress", "segments": 8}).json()["id"]
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("UPDATE clocks SET filled = 7 WHERE id = %s", (cid,))
        conn.close()
        resp = client.patch(f"/api/clocks/{cid}", json={"segments": 4}).json()
        assert resp["segments"] == 4 and resp["filled"] == 4

    def test_lifecycle_resolve_and_reactivate(self):
        cid = client.post("/api/clocks", json={"name": "D", "kind": "progress", "segments": 4}).json()["id"]
        done = client.patch(f"/api/clocks/{cid}/lifecycle",
                            json={"lifecycle": "resolved", "resolution": "objective reached"}).json()
        assert done["lifecycle"] == "resolved" and done["resolved_at"] is not None
        back = client.patch(f"/api/clocks/{cid}/lifecycle", json={"lifecycle": "active"}).json()
        assert back["lifecycle"] == "active" and back["resolved_at"] is None


class TestTickRoutes:
    def test_tick_and_history(self):
        cid = client.post("/api/clocks", json={"name": "Recall", "kind": "countdown", "segments": 8}).json()["id"]
        r1 = client.post(f"/api/clocks/{cid}/ticks", json={"delta": -1, "reason": "End of watch"})
        r2 = client.post(f"/api/clocks/{cid}/ticks", json={"delta": -1, "reason": "Hazard: taint pocket"})
        assert r1.status_code == 200 and r2.status_code == 200
        history = client.get(f"/api/clocks/{cid}/ticks").json()
        assert [t["reason"] for t in history] == ["Hazard: taint pocket", "End of watch"]

    def test_tick_requires_reason(self):
        cid = client.post("/api/clocks", json={"name": "E", "kind": "progress", "segments": 4}).json()["id"]
        assert client.post(f"/api/clocks/{cid}/ticks", json={"delta": 1, "reason": ""}).status_code == 422

    def test_tick_on_resolved_clock_409(self):
        cid = client.post("/api/clocks", json={"name": "F", "kind": "progress", "segments": 4}).json()["id"]
        client.patch(f"/api/clocks/{cid}/lifecycle", json={"lifecycle": "resolved", "resolution": "x"})
        assert client.post(f"/api/clocks/{cid}/ticks", json={"delta": 1, "reason": "y"}).status_code == 409


class TestLinks:
    def test_link_clock_to_thread_and_detail_shows_it(self):
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO threads (id, title, status, priority)
                VALUES ('th-clock-test', 'Clock Thread', 'active', 'med')
                """
            )
        conn.close()
        cid = client.post("/api/clocks", json={"name": "G", "kind": "progress", "segments": 4}).json()["id"]
        resp = client.post(
            f"/api/clocks/{cid}/links",
            json={"target_endpoint": "thread:th-clock-test", "relationship_type": "tracks"},
        )
        assert resp.status_code == 200
        detail = client.get(f"/api/clocks/{cid}").json()
        assert detail["links"][0]["target_id"] == "thread:th-clock-test"
        rel_id = detail["links"][0]["id"]
        assert client.delete(f"/api/clocks/{cid}/links/{rel_id}").status_code == 200
        assert client.get(f"/api/clocks/{cid}").json()["links"] == []

    def test_link_rejects_bad_endpoint_prefix(self):
        cid = client.post("/api/clocks", json={"name": "H", "kind": "progress", "segments": 4}).json()["id"]
        resp = client.post(f"/api/clocks/{cid}/links",
                           json={"target_endpoint": "widget:nope", "relationship_type": "tracks"})
        assert resp.status_code == 422


class TestTickRouteAtomicity:
    def test_failed_fire_rolls_back_all_writes(self, monkeypatch):
        import gm_dashboard.clock_engine as engine

        trigger = client.post(
            "/api/clocks", json={"name": "Trig", "kind": "progress", "segments": 4}
        ).json()
        target = client.post(
            "/api/clocks", json={"name": "Targ", "kind": "progress", "segments": 4}
        ).json()
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cascade_rules
                  (name, title, trigger_kind, trigger_clock_id, trigger_event, effects)
                VALUES ('atomicity-rule', 'Atomicity', 'clock_event', %s, 'ticked', %s)
                """,
                (
                    trigger["id"],
                    psycopg2.extras.Json(
                        [{"clock_id": target["id"], "delta": 1, "reason_template": "cascade"}]
                    ),
                ),
            )
        conn.close()

        real_write = engine._write_fire_result

        def exploding_write(cur, fire_id, result):
            real_write(cur, fire_id, result)  # rows written inside the transaction
            raise RuntimeError("boom: injected mid-fire failure")

        monkeypatch.setattr(engine, "_write_fire_result", exploding_write)

        crashy_client = TestClient(app, raise_server_exceptions=False)
        resp = crashy_client.post(
            f"/api/clocks/{trigger['id']}/ticks", json={"delta": 1, "reason": "tick"}
        )
        assert resp.status_code == 500

        conn = _connect()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT count(*) AS n FROM clock_ticks")
            assert cur.fetchone()["n"] == 0
            cur.execute("SELECT filled FROM clocks WHERE id = %s", (trigger["id"],))
            assert cur.fetchone()["filled"] == 0
            cur.execute("SELECT filled FROM clocks WHERE id = %s", (target["id"],))
            assert cur.fetchone()["filled"] == 0
        conn.close()


class TestCascadeRoutes:
    def _mk_clocks(self):
        a = client.post("/api/clocks", json={"name": "Corruption", "kind": "progress", "segments": 8}).json()
        b = client.post("/api/clocks", json={"name": "Trade", "kind": "countdown", "segments": 8}).json()
        return a["id"], b["id"]

    def test_create_and_list_rule(self):
        a, b = self._mk_clocks()
        resp = client.post("/api/cascades", json={
            "name": "failed-patrol", "title": "Failed Patrol",
            "trigger_kind": "manual",
            "effects": [
                {"clock_id": a, "delta": 1, "reason_template": "Failed patrol"},
                {"clock_id": b, "delta": -1, "reason_template": "Failed patrol"},
            ],
        })
        assert resp.status_code == 200
        rules = client.get("/api/cascades").json()
        assert [r["name"] for r in rules] == ["failed-patrol"]

    def test_condition_validated_on_save(self):
        a, _ = self._mk_clocks()
        resp = client.post("/api/cascades", json={
            "name": "bad-cond", "trigger_kind": "manual",
            "condition": {"clock": a, "op": "between", "value": 2},
            "effects": [{"clock_id": a, "delta": 1, "reason_template": "x"}],
        })
        assert resp.status_code == 422

    def test_clock_event_rule_requires_clock_and_event(self):
        a, _ = self._mk_clocks()
        resp = client.post("/api/cascades", json={
            "name": "no-event", "trigger_kind": "clock_event",
            "effects": [{"clock_id": a, "delta": 1, "reason_template": "x"}],
        })
        assert resp.status_code == 422

    def test_effects_must_reference_existing_clocks(self):
        resp = client.post("/api/cascades", json={
            "name": "ghost", "trigger_kind": "manual",
            "effects": [{"clock_id": "00000000-0000-0000-0000-000000000000",
                         "delta": 1, "reason_template": "x"}],
        })
        assert resp.status_code == 422

    def test_fire_dry_run_then_apply(self):
        a, b = self._mk_clocks()
        rid = client.post("/api/cascades", json={
            "name": "failed-patrol-2", "title": "Failed Patrol",
            "trigger_kind": "manual",
            "effects": [
                {"clock_id": a, "delta": 1, "reason_template": "Failed patrol ({trigger_note})"},
                {"clock_id": b, "delta": -1, "reason_template": "Failed patrol ({trigger_note})"},
            ],
        }).json()["id"]
        preview = client.post(f"/api/cascades/{rid}/fire",
                              json={"dry_run": True, "trigger_note": "s12"}).json()
        assert preview["dry_run"] is True and len(preview["applied"]) == 2
        assert client.get(f"/api/clocks/{a}").json()["filled"] == 0  # nothing written
        applied = client.post(f"/api/cascades/{rid}/fire",
                              json={"dry_run": False, "trigger_note": "s12"}).json()
        assert applied["dry_run"] is False
        assert client.get(f"/api/clocks/{a}").json()["filled"] == 1
        assert client.get(f"/api/clocks/{b}").json()["filled"] == 7

    def test_fire_clock_event_rule_directly_422(self):
        a, _ = self._mk_clocks()
        rid = client.post("/api/cascades", json={
            "name": "evt", "trigger_kind": "clock_event",
            "trigger_clock_id": a, "trigger_event": "filled",
            "effects": [{"clock_id": a, "delta": 1, "reason_template": "x"}],
        }).json()["id"]
        resp = client.post(f"/api/cascades/{rid}/fire", json={"dry_run": False})
        assert resp.status_code == 422

    def test_delete_rule(self):
        a, _ = self._mk_clocks()
        rid = client.post("/api/cascades", json={
            "name": "temp", "trigger_kind": "manual",
            "effects": [{"clock_id": a, "delta": 1, "reason_template": "x"}],
        }).json()["id"]
        assert client.delete(f"/api/cascades/{rid}").status_code == 200
        assert client.get("/api/cascades").json() == []

    def _mk_rule(self, clock_id):
        return client.post("/api/cascades", json={
            "name": "patchable", "trigger_kind": "manual",
            "effects": [{"clock_id": clock_id, "delta": 1, "reason_template": "x"}],
        }).json()["id"]

    def test_patch_garbage_trigger_kind_422(self):
        a, _ = self._mk_clocks()
        rid = self._mk_rule(a)
        resp = client.patch(f"/api/cascades/{rid}", json={"trigger_kind": "banana"})
        assert resp.status_code == 422

    def test_patch_empty_effects_422(self):
        a, _ = self._mk_clocks()
        rid = self._mk_rule(a)
        resp = client.patch(f"/api/cascades/{rid}", json={"effects": []})
        assert resp.status_code == 422

    def test_patch_zero_delta_effect_422(self):
        a, _ = self._mk_clocks()
        rid = self._mk_rule(a)
        resp = client.patch(f"/api/cascades/{rid}", json={
            "effects": [{"clock_id": a, "delta": 0, "reason_template": "x"}],
        })
        assert resp.status_code == 422

    def test_patch_to_clock_event_without_trigger_fields_422(self):
        a, _ = self._mk_clocks()
        rid = self._mk_rule(a)
        resp = client.patch(f"/api/cascades/{rid}", json={"trigger_kind": "clock_event"})
        assert resp.status_code == 422

    def test_patch_valid_update_200(self):
        a, b = self._mk_clocks()
        rid = self._mk_rule(a)
        resp = client.patch(f"/api/cascades/{rid}", json={
            "title": "Patched",
            "effects": [{"clock_id": b, "delta": -2, "reason_template": "y"}],
        })
        assert resp.status_code == 200
        out = resp.json()
        assert out["title"] == "Patched"
        assert out["effects"] == [{"clock_id": b, "delta": -2, "reason_template": "y"}]


class TestThreadIntegration:
    def test_thread_detail_includes_linked_clock_and_divergence(self):
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO threads (id, title, status, priority,
                                     clock_label, clock_value, clock_max)
                VALUES ('th-linked', 'Linked Thread', 'active', 'med', 'Pressure', 2, 6)
                """
            )
        conn.close()
        cid = client.post("/api/clocks", json={"name": "Pressure", "kind": "progress",
                                               "segments": 6}).json()["id"]
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("UPDATE clocks SET origin = 'thread_migration', filled = 2 WHERE id = %s", (cid,))
        conn.close()
        client.post(f"/api/clocks/{cid}/links",
                    json={"target_endpoint": "thread:th-linked", "relationship_type": "tracks"})

        detail = client.get("/api/threads/th-linked").json()
        assert detail["linked_clocks"][0]["name"] == "Pressure"
        assert detail["linked_clocks"][0]["legacy_divergence"] is False

        client.post(f"/api/clocks/{cid}/ticks", json={"delta": 1, "reason": "escalation"})
        detail = client.get("/api/threads/th-linked").json()
        assert detail["linked_clocks"][0]["legacy_divergence"] is True
