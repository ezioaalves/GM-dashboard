from __future__ import annotations

import os

import psycopg2
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm")
from gm_dashboard.api import app
from gm_dashboard.campaign.proposals import STRATEGIES, FallbackStrategy, ReviewGatedSurfaceStrategy, TruthUpdateStrategy

client = TestClient(app)


def _clean() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM creative_proposal_audits")
        cursor.execute("DELETE FROM creative_proposals")
        cursor.execute("DELETE FROM campaign_truths")
        cursor.execute("DELETE FROM sync_reviews WHERE review_type = 'creative_proposal'")
        cursor.execute("DELETE FROM sync_jobs WHERE job_type = 'creative_proposal'")
    conn.close()


@pytest.fixture(autouse=True)
def proposals_db():
    _clean()
    yield
    _clean()


def _query(sql: str, params=()) -> list[tuple]:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    conn.close()
    return rows


def _accepted_proposal(**overrides) -> dict:
    payload = {
        "title": "Test proposal", "target_type": "note", "target_id": "note-1",
        "proposed_changes": {"body": "text"}, **overrides,
    }
    proposal = client.post("/api/creative-proposals", json=payload).json()
    decided = client.post(f"/api/creative-proposals/{proposal['id']}/decision", json={"decision": "accept"})
    assert decided.status_code == 200
    return decided.json()


def test_strategy_order_puts_review_gate_before_truth_and_fallback():
    assert isinstance(STRATEGIES[0], ReviewGatedSurfaceStrategy)
    assert isinstance(STRATEGIES[1], TruthUpdateStrategy)
    assert isinstance(STRATEGIES[2], FallbackStrategy)


@pytest.mark.parametrize("surface", ["vault", "foundry_test", "foundry_prod"])
def test_vault_and_foundry_targets_create_review_without_job_or_mutation(surface):
    proposal = _accepted_proposal(target_surface=surface, target_type="truth", target_id="doc-1")
    res = client.post(f"/api/creative-proposals/{proposal['id']}/apply")
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["state"] == "review_required"

    reviews = _query(
        "SELECT target_surface, review_status FROM sync_reviews WHERE review_type = 'creative_proposal'"
    )
    assert reviews == [(surface, "pending")]
    # Review creation is the whole outcome: no execution job and no truth
    # mutation, even when the target_type would match the truth strategy.
    assert _query("SELECT count(*) FROM sync_jobs WHERE job_type = 'creative_proposal'") == [(0,)]
    assert _query("SELECT count(*) FROM campaign_truths") == [(0,)]


def test_truth_target_updates_only_allowed_fields():
    truth = client.post("/api/truths", json={"key": "k1", "statement": "Old"}).json()
    proposal = _accepted_proposal(
        target_type="truth", target_id=truth["id"],
        proposed_changes={"statement": "New", "state": "locked", "key": "hacked", "source": "hacked"},
    )
    res = client.post(f"/api/creative-proposals/{proposal['id']}/apply")
    assert res.status_code == 200
    assert res.json()["result"] == {"truth_id": truth["id"], "state": "applied"}

    updated = client.get("/api/truths").json()[0]
    assert updated["statement"] == "New"
    assert updated["state"] == "locked"
    assert updated["key"] == "k1"
    assert updated["source"] == "manual"
    assert _query("SELECT count(*) FROM sync_reviews WHERE review_type = 'creative_proposal'") == [(0,)]


def test_truth_target_validation_and_missing_truth():
    malformed = _accepted_proposal(target_type="truth", target_id="not-a-uuid")
    assert client.post(f"/api/creative-proposals/{malformed['id']}/apply").status_code == 422

    missing = _accepted_proposal(target_type="truth", target_id="00000000-0000-0000-0000-000000000000")
    assert client.post(f"/api/creative-proposals/{missing['id']}/apply").status_code == 404


def test_fallback_applies_remaining_targets_and_records_audit():
    proposal = _accepted_proposal(target_type="note", target_id="note-9")
    res = client.post(f"/api/creative-proposals/{proposal['id']}/apply")
    assert res.status_code == 200
    body = res.json()
    assert body["result"] == {"state": "applied", "target_type": "note", "target_id": "note-9"}
    assert body["state"] == "applied"
    assert body["audit_id"]
    audits = _query("SELECT action FROM creative_proposal_audits WHERE proposal_id = %s", (proposal["id"],))
    assert ("apply",) in audits


def test_apply_requires_accepted_state():
    proposal = client.post(
        "/api/creative-proposals",
        json={"title": "Pending", "target_type": "note", "target_id": "note-2"},
    ).json()
    assert client.post(f"/api/creative-proposals/{proposal['id']}/apply").status_code == 409
