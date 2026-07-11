from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

from gm_dashboard.event_scan import scan_events, parse_events_file

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
)

TABLES_TO_CLEAN = ["scenes", "sync_reviews", "clocks"]


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


def _write(tmp_path: Path, rel: str, content: str) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


EVENTS_MD = """# Event Library

## Live Pressures

- Selection Readiness.

## How To Use An Event

Meta section, skipped.

## Selection Readiness - Continuous Evaluation Begins

### Trigger

Use when the PCs ask what matters for Ogushi Shiken.

### Cast

- PCs.
- One evaluator.

### Outputs

Choose one:

- Clear direction.
"""


def test_parse_events_file_extracts_modules_and_skips_meta_sections():
    modules = parse_events_file(EVENTS_MD)
    assert [m["title"] for m in modules] == ["Selection Readiness - Continuous Evaluation Begins"]
    assert "Use when the PCs ask" in modules[0]["body"]
    assert "### Outputs" in modules[0]["body"]


def test_scan_events_dry_run_reports_summary(tmp_path):
    _write(
        tmp_path,
        "Campaign Management/01 - Live/Current Arc/The Training Arc/_Play Aids/Event Library.md",
        EVENTS_MD,
    )
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_events(tmp_path, cur, dry_run=True)
    finally:
        conn.close()
    assert summary["scanned"] == 1
    assert summary["new"] == 1


from fastapi.testclient import TestClient
from gm_dashboard.api import app

client = TestClient(app)


def test_scan_and_apply_event_import_links_matching_clock(tmp_path, monkeypatch):
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO clocks (name, segments) VALUES ('Selection Readiness', 5)"
            )
    finally:
        conn.close()

    _write(
        tmp_path,
        "Campaign Management/01 - Live/Current Arc/The Training Arc/_Play Aids/Event Library.md",
        EVENTS_MD,
    )
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    scan_res = client.post("/api/scenes/import/scan")
    assert scan_res.status_code == 200
    review_id = scan_res.json()["review_ids"][0]

    client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    apply_res = client.post(f"/api/sync/reviews/{review_id}/apply", json={"confirmation": True})
    assert apply_res.status_code == 200

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT title, placement, clock FROM scenes")
            row = cur.fetchone()
    finally:
        conn.close()
    assert row["title"] == "Selection Readiness - Continuous Evaluation Begins"
    assert row["placement"] == "backlog"
    assert "Selection Readiness" in row["clock"]
