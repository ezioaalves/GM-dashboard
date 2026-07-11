# backend/tests/test_clock_scan.py
from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

from gm_dashboard.clock_scan import scan_clocks, parse_clocks_file

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
)

TABLES_TO_CLEAN = ["clocks", "sync_reviews"]


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


CLOCKS_MD = """# Clocks and Beats

## How To Use A Clock

Meta section, skipped.

## Kanimaru Public Rivalry

| Segment | Beat | Impact |
| --- | --- | --- |
| 1 | Kubo sees Kanimaru's standard. | Kanimaru becomes visible. |
| 2 | Kanimaru frames Kubo. | Kubo gets social pressure. |

**If PCs ignore it:** Kanimaru's narrative becomes default truth.

**If PCs engage early:** move the duel earlier.

## Clock Review After Every Session

Meta section, skipped.
"""


def test_parse_clocks_file_extracts_named_clocks_and_skips_meta_sections():
    clocks = parse_clocks_file(CLOCKS_MD)
    assert [c["name"] for c in clocks] == ["Kanimaru Public Rivalry"]
    assert clocks[0]["segments"] == 2
    assert "Kubo sees Kanimaru's standard." in clocks[0]["description"]
    assert "If PCs ignore it" in clocks[0]["description"]


def test_scan_clocks_dry_run_reports_summary_without_writing(tmp_path):
    _write(
        tmp_path,
        "Campaign Management/01 - Live/Current Arc/The Training Arc/_Play Aids/Clocks and Beats.md",
        CLOCKS_MD,
    )
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_clocks(tmp_path, cur, dry_run=True)
            cur.execute("SELECT count(*) AS n FROM sync_reviews")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert summary == {"scanned": 1, "new": 1, "duplicate_pending": 0, "review_ids": []}
    assert count == 0


from fastapi.testclient import TestClient
from gm_dashboard.api import app

client = TestClient(app)


def test_scan_and_apply_clock_import(tmp_path, monkeypatch):
    _write(
        tmp_path,
        "Campaign Management/01 - Live/Current Arc/The Training Arc/_Play Aids/Clocks and Beats.md",
        CLOCKS_MD,
    )
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    scan_res = client.post("/api/clocks/import/scan")
    assert scan_res.status_code == 200
    review_id = scan_res.json()["review_ids"][0]

    client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    apply_res = client.post(f"/api/sync/reviews/{review_id}/apply", json={"confirmation": True})
    assert apply_res.status_code == 200

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT name, segments, filled FROM clocks")
            row = cur.fetchone()
    finally:
        conn.close()
    assert row["name"] == "Kanimaru Public Rivalry"
    assert row["segments"] == 2
    assert row["filled"] == 0
