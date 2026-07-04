from __future__ import annotations

import os

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
