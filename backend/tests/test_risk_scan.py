# backend/tests/test_risk_scan.py
from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

from gm_dashboard.risk_scan import scan_risks

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
)

TABLES_TO_CLEAN = ["risks", "sync_reviews", "sessions"]


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


RISKS_MD = """# Campaign Risk Register

Intro paragraph, ignored.

| Risk | Likelihood | Mitigation | Contingency | Last reviewed |
| --- | --- | --- | --- | --- |
| Social contract remains implicit. | Medium | Review the framework with players. | Make a ruling and log a decision. | 2026-06-10 |
| Foundry state drifts from vault source of truth. | Medium | Treat vault as canonical. | Re-import from vault. | 2026-06-10 |

## Review Checklist

Ignored section.
"""


def test_scan_risks_dry_run_reports_summary_without_writing_reviews(tmp_path):
    _write(tmp_path, "Campaign Management/operational/risks.md", RISKS_MD)

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_risks(tmp_path, cur, dry_run=True)
            cur.execute("SELECT count(*) AS n FROM sync_reviews")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert summary == {"scanned": 2, "new": 2, "duplicate_pending": 0, "review_ids": []}
    assert count == 0


from fastapi.testclient import TestClient
from gm_dashboard.api import app

client = TestClient(app)


def test_scan_risks_creates_pending_reviews_and_skips_on_rescan(tmp_path, monkeypatch):
    _write(tmp_path, "Campaign Management/operational/risks.md", RISKS_MD)
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    res = client.post("/api/risks/import/scan")
    assert res.status_code == 200
    body = res.json()
    assert body["new"] == 2
    assert body["duplicate_pending"] == 0

    res2 = client.post("/api/risks/import/scan")
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["new"] == 0
    assert body2["duplicate_pending"] == 2


def test_apply_risk_import_creates_risk_row(tmp_path, monkeypatch):
    _write(tmp_path, "Campaign Management/operational/risks.md", RISKS_MD)
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    scan_res = client.post("/api/risks/import/scan")
    review_id = scan_res.json()["review_ids"][0]

    client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    apply_res = client.post(f"/api/sync/reviews/{review_id}/apply", json={"confirmation": True})
    assert apply_res.status_code == 200

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT title, likelihood FROM risks")
            risk = cur.fetchone()
    finally:
        conn.close()
    assert risk["title"] == "Social contract remains implicit."
    assert risk["likelihood"] == "medium"
