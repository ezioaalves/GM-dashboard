from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

from gm_dashboard.session_scan import parse_session_log, scan_sessions

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
)

TABLES_TO_CLEAN = ["session_notes", "sessions", "sync_reviews"]


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


SESSION_MD = """---
schema_version: 1
session: 17
date: 2026-06-15
title: "Red in the Forest"
threads:
  advanced: [shadowlands-escalation]
  planted: [deeper-jigoku-force]
  resolved: []
npcs_present:
  - Dattoumaru_Zanzou
locations:
  - Yoimura_Wall
has_secret: true
---

# Session 17 - Red in the Forest

## What happened

The patrol went badly wrong.

## Notable moments

- Kanimaru's first sighting.
- The Tetsu no Oni appeared.

## NPCs in play

- [[Dattoumaru_Zanzou]] - briefed the patrol.
"""


def test_parse_session_log_extracts_frontmatter_and_sections(tmp_path):
    path = tmp_path / "17-red-in-the-forest.md"
    parsed = parse_session_log(SESSION_MD, path)
    assert parsed is not None
    assert parsed["session"]["number"] == 17
    assert parsed["session"]["name"] == "Red in the Forest"
    assert parsed["session"]["date"] == "2026-06-15"
    assert "patrol went badly wrong" in parsed["session"]["summary"]
    assert parsed["session_note"]["npcs_present"] == ["Dattoumaru_Zanzou"]
    assert parsed["session_note"]["threads_touched"] == [
        "shadowlands-escalation",
        "deeper-jigoku-force",
    ]
    assert parsed["session_note"]["scenes"] == [
        "Kanimaru's first sighting.",
        "The Tetsu no Oni appeared.",
    ]


def test_parse_session_log_returns_none_without_session_number(tmp_path):
    path = tmp_path / "no-number.md"
    assert parse_session_log("# Untitled\n\nNo frontmatter here.", path) is None


def test_scan_sessions_dry_run_reports_summary(tmp_path):
    _write(tmp_path, "Campaign Management/session-logs/17-red-in-the-forest.md", SESSION_MD)
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_sessions(tmp_path, cur, dry_run=True)
    finally:
        conn.close()
    assert summary["scanned"] == 1
    assert summary["new"] == 1
    assert summary["review_ids"] == []


def test_scan_sessions_skips_secret_and_draft_logs(tmp_path):
    _write(tmp_path, "Campaign Management/session-logs/17-red-in-the-forest.md", SESSION_MD)
    _write(tmp_path, "Campaign Management/session-logs/17-red-in-the-forest.secret.md", SESSION_MD)
    _write(tmp_path, "Campaign Management/session-logs/_drafts/18-draft.md", SESSION_MD)
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_sessions(tmp_path, cur, dry_run=True)
    finally:
        conn.close()
    assert summary["scanned"] == 1


from fastapi.testclient import TestClient
from gm_dashboard.api import app

client = TestClient(app)


def test_scan_and_apply_session_import_creates_session_and_note(tmp_path, monkeypatch):
    _write(tmp_path, "Campaign Management/session-logs/17-red-in-the-forest.md", SESSION_MD)
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    scan_res = client.post("/api/sessions/import/scan")
    assert scan_res.status_code == 200
    review_ids = scan_res.json()["review_ids"]
    assert len(review_ids) == 1
    review_id = review_ids[0]

    client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    apply_res = client.post(f"/api/sync/reviews/{review_id}/apply", json={"confirmation": True})
    assert apply_res.status_code == 200

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, number, name, summary FROM sessions WHERE number = 17")
            session = cur.fetchone()
            cur.execute(
                "SELECT npcs_present, threads_touched FROM session_notes WHERE session_id = %s",
                (session["id"],),
            )
            note = cur.fetchone()
    finally:
        conn.close()

    assert session["name"] == "Red in the Forest"
    assert "patrol went badly wrong" in session["summary"]
    assert note["npcs_present"] == ["Dattoumaru_Zanzou"]
    assert note["threads_touched"] == ["shadowlands-escalation", "deeper-jigoku-force"]


def test_scan_and_apply_session_import_handles_session_number_zero(tmp_path, monkeypatch):
    zero_session_md = SESSION_MD.replace("session: 17", "session: 0")
    _write(tmp_path, "Campaign Management/session-logs/00-character-creation.md", zero_session_md)
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    scan_res = client.post("/api/sessions/import/scan")
    review_id = scan_res.json()["review_ids"][0]
    client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    apply_res = client.post(f"/api/sync/reviews/{review_id}/apply", json={"confirmation": True})

    assert apply_res.status_code == 200
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT number FROM sessions WHERE number = 0")
            row = cur.fetchone()
    finally:
        conn.close()
    assert row is not None


def test_rescan_after_apply_reports_unchanged(tmp_path, monkeypatch):
    _write(tmp_path, "Campaign Management/session-logs/17-red-in-the-forest.md", SESSION_MD)
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    scan_res = client.post("/api/sessions/import/scan")
    review_id = scan_res.json()["review_ids"][0]
    client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    client.post(f"/api/sync/reviews/{review_id}/apply", json={"confirmation": True})

    rescan_res = client.post("/api/sessions/import/scan")
    assert rescan_res.status_code == 200
    summary = rescan_res.json()
    assert summary["unchanged"] == 1
    assert summary["new"] == 0
    assert summary["changed"] == 0
