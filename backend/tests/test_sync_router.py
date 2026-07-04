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
        cur.execute("DELETE FROM tickets")
        cur.execute("DELETE FROM threads")
        cur.execute("DELETE FROM lore_relationships")
        cur.execute("DELETE FROM lore_entities")
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
    conn.close()


@pytest.fixture(autouse=True)
def clean_sync_tables():
    _clean()
    yield
    _clean()


FULL_TICKET_PAYLOAD = {
    "id": "sync-router-test-ticket",
    "title": "Sync Router Test Ticket",
    "status": "open",
    "area": "housekeeping",
    "priority": "high",
    "stage": "next",
    "parent_id": None,
    "threads": [],
    "depends_on": [],
    "next_action": "Write tests",
    "resume_note": "",
    "source": "vault",
    "introduced": None,
    "closed": None,
    "resolution": "",
    "review_after": None,
    "lane": "next",
    "classification": "",
    "target_epic": "",
    "source_path": "Campaign Management/operational/tickets/sync-router-test-ticket.md",
    "source_hash": "hash-a",
    "source_mtime": None,
    "body": "Body text.",
}


def _seed_review(**overrides) -> dict:
    base = {
        "review_type": "relationship_change",
        "source_surface": "manual",
        "target_surface": "postgres",
        "target_type": "relationship",
        "target_id": "",
        "proposed_changes": {},
    }
    base.update(overrides)
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  proposed_changes, review_status
                )
                VALUES (
                  %(review_type)s, %(source_surface)s, %(target_surface)s, %(target_type)s,
                  %(target_id)s, %(proposed_changes)s, %(review_status)s
                )
                RETURNING *
                """,
                {
                    **base,
                    "review_status": overrides.get("review_status", "pending"),
                    "proposed_changes": psycopg2.extras.Json(base["proposed_changes"]),
                },
            )
            return dict(cur.fetchone())
    finally:
        conn.close()


def test_get_sync_review_404_for_unknown_id():
    missing = client.get("/api/sync/reviews/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


def test_get_sync_job_404_for_unknown_id():
    missing = client.get("/api/sync/jobs/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


def test_list_sync_reviews_filters_by_status_type_and_target_type():
    _seed_review(review_type="ticket_import", target_type="ticket", review_status="pending")
    _seed_review(review_type="thread_import", target_type="thread", review_status="accepted")

    by_status = client.get("/api/sync/reviews?review_status=accepted")
    assert by_status.status_code == 200
    assert [row["review_type"] for row in by_status.json()] == ["thread_import"]

    by_type = client.get("/api/sync/reviews?review_type=ticket_import&target_type=ticket")
    assert by_type.status_code == 200
    assert len(by_type.json()) == 1

    limited = client.get("/api/sync/reviews?limit=1")
    assert limited.status_code == 200
    assert len(limited.json()) == 1


def test_decide_sync_review_rejects_invalid_status():
    review = _seed_review()
    res = client.patch(
        f"/api/sync/reviews/{review['id']}",
        json={"review_status": "made_up"},
    )
    assert res.status_code == 422


def test_decide_sync_review_404_for_unknown_review():
    res = client.patch(
        "/api/sync/reviews/00000000-0000-0000-0000-000000000000",
        json={"review_status": "accepted"},
    )
    assert res.status_code == 404


def test_decide_sync_review_records_decision_and_timestamp():
    review = _seed_review()
    res = client.patch(
        f"/api/sync/reviews/{review['id']}",
        json={"review_status": "rejected", "decision": {"note": "not needed"}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["review_status"] == "rejected"
    assert body["decision"]["note"] == "not needed"
    assert body["decided_at"] is not None


def test_apply_review_requires_confirmation():
    review = _seed_review(review_status="accepted")
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={})
    assert res.status_code == 422


def test_apply_review_404_for_unknown_review():
    res = client.post(
        "/api/sync/reviews/00000000-0000-0000-0000-000000000000/apply",
        json={"confirmation": True},
    )
    assert res.status_code == 404


def test_apply_review_rejects_when_not_accepted_or_merged():
    review = _seed_review(review_status="pending")
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409


def test_apply_review_rejects_target_surface_mismatch():
    review = _seed_review(review_status="accepted", target_surface="postgres")
    res = client.post(
        f"/api/sync/reviews/{review['id']}/apply",
        json={"confirmation": True, "target_surface": "vault"},
    )
    assert res.status_code == 409


def test_apply_ticket_import_creates_ticket_and_marks_review_applied():
    review = _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        target_id="sync-router-test-ticket",
        review_status="accepted",
        proposed_changes={"ticket": FULL_TICKET_PAYLOAD},
    )

    applied = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert applied.status_code == 200
    body = applied.json()
    assert body["applied"] is True
    assert body["ticket_id"] == "sync-router-test-ticket"
    assert body["sync_job_id"]

    ticket = client.get("/api/tickets/sync-router-test-ticket")
    assert ticket.status_code == 200
    assert ticket.json()["review_status"] == "accepted"

    review_detail = client.get(f"/api/sync/reviews/{review['id']}")
    assert review_detail.status_code == 200
    assert review_detail.json()["applied_at"] is not None
    assert review_detail.json()["review_status"] == "accepted"

    job = client.get(f"/api/sync/jobs/{body['sync_job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"


def test_apply_ticket_import_without_ticket_payload_returns_409():
    review = _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        review_status="accepted",
        proposed_changes={},
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409


def test_apply_review_is_idempotent_and_returns_already_applied_result():
    review = _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        target_id="sync-router-test-ticket",
        review_status="accepted",
        proposed_changes={"ticket": FULL_TICKET_PAYLOAD},
    )
    first = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert first.status_code == 200

    second = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["already_applied"] is True
    assert second_body["sync_job_id"] == first.json()["sync_job_id"]


def test_apply_review_blocks_and_records_error_for_unsupported_review_type():
    review = _seed_review(
        review_type="asset_import",
        target_type="asset",
        review_status="accepted",
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409
    assert "asset_import" in res.json()["detail"]

    freshness = client.get("/api/sync/freshness")
    assert freshness.status_code == 200
    assert freshness.json()["counts"]["blocked_jobs"] == 1


def test_sync_freshness_prioritizes_conflict_over_other_states():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, review_status
                )
                VALUES ('vault_import', 'vault', 'postgres', 'entity', 'conflict')
                """
            )
            cur.execute(
                """
                INSERT INTO sync_jobs (target, direction, status)
                VALUES ('entity:conflict-test', 'vault_to_postgres', 'failed')
                """
            )
    finally:
        conn.close()

    res = client.get("/api/sync/freshness")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "conflict"
    assert data["counts"]["conflict_reviews"] == 1
    assert data["counts"]["failed_jobs"] == 1


def test_sync_freshness_reports_fresh_when_nothing_outstanding():
    res = client.get("/api/sync/freshness")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "fresh"
    assert data["items"] == []
