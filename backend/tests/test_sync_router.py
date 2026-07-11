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
        cur.execute("DELETE FROM lore_aliases")
        cur.execute("DELETE FROM lore_sections")
        cur.execute("DELETE FROM lore_entities")
        cur.execute("DELETE FROM lore_sources")
        cur.execute("DELETE FROM lore_assets")
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
        "base_version": "",
        "current_version": "",
        "proposed_changes": {},
        "conflict_flags": [],
    }
    base.update(overrides)
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  base_version, current_version, proposed_changes, conflict_flags, review_status
                )
                VALUES (
                  %(review_type)s, %(source_surface)s, %(target_surface)s, %(target_type)s,
                  %(target_id)s, %(base_version)s, %(current_version)s,
                  %(proposed_changes)s, %(conflict_flags)s, %(review_status)s
                )
                RETURNING *
                """,
                {
                    **base,
                    "review_status": overrides.get("review_status", "pending"),
                    "proposed_changes": psycopg2.extras.Json(base["proposed_changes"]),
                    "conflict_flags": psycopg2.extras.Json(base["conflict_flags"]),
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


def test_apply_ticket_import_with_missing_parent_returns_clean_409():
    review = _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        target_id="child-ticket",
        review_status="accepted",
        proposed_changes={
            "ticket": {
                **FULL_TICKET_PAYLOAD,
                "id": "child-ticket",
                "parent_id": "parent-not-imported-yet",
            }
        },
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409
    assert "parent-not-imported-yet" in res.json()["detail"]

    ticket = client.get("/api/tickets/child-ticket")
    assert ticket.status_code == 404


def test_apply_ticket_import_with_already_imported_parent_succeeds():
    _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        target_id="parent-ticket",
        review_status="accepted",
        proposed_changes={"ticket": {**FULL_TICKET_PAYLOAD, "id": "parent-ticket"}},
    )
    parent_review = client.get("/api/sync/reviews?review_type=ticket_import&target_type=ticket")
    parent_id = next(r["id"] for r in parent_review.json() if r["target_id"] == "parent-ticket")
    client.post(f"/api/sync/reviews/{parent_id}/apply", json={"confirmation": True})

    child_review = _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        target_id="child-ticket-2",
        review_status="accepted",
        proposed_changes={
            "ticket": {
                **FULL_TICKET_PAYLOAD,
                "id": "child-ticket-2",
                "parent_id": "parent-ticket",
            }
        },
    )
    res = client.post(f"/api/sync/reviews/{child_review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 200
    assert res.json()["applied"] is True


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
        review_type="totally_unsupported_type",
        target_type="asset",
        review_status="accepted",
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409
    assert "totally_unsupported_type" in res.json()["detail"]

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


VAULT_IMPORT_PAYLOAD = {
    "diff_kind": "new",
    "entity": {"slug": "kanigakure", "title": "Kanigakure", "entity_type": "location"},
    "sections": [
        {
            "heading": "Overview",
            "body": "Home base.",
            "section_order": 0,
            "heading_path": ["Overview"],
            "start_line": 3,
            "end_line": 5,
        }
    ],
    "relationships": [
        {
            "source_type": "entity",
            "target_type": "entity",
            "relationship_type": "mentions",
            "provenance": "wikilink",
            "unresolved_target": "Someone Else",
        }
    ],
    "source_paths": ["Lore/World_of_Rokugan/Locations/Kani.md"],
    "metadata": {},
}


def test_apply_vault_import_creates_entity_sections_and_relationships():
    review = _seed_review(
        review_type="vault_import",
        target_type="entity",
        target_id="",
        base_version="",
        current_version="hash-a",
        review_status="accepted",
        proposed_changes=VAULT_IMPORT_PAYLOAD,
    )

    applied = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert applied.status_code == 200
    body = applied.json()
    assert body["applied"] is True
    assert body["entity_id"]
    assert body["source_id"]
    assert len(body["relationship_ids"]) == 1

    entity = client.get(f"/api/lore/entities/{body['entity_id']}")
    assert entity.status_code == 200
    entity_body = entity.json()
    assert entity_body["slug"] == "kanigakure"
    assert entity_body["source_hash"] == "hash-a"
    assert [s["heading"] for s in entity_body["sections"]] == ["Overview"]
    assert len(entity_body["relationships"]) == 1
    assert entity_body["relationships"][0]["unresolved_target"] == "Someone Else"


def test_apply_vault_import_without_entity_payload_returns_409():
    review = _seed_review(
        review_type="vault_import",
        target_type="entity",
        review_status="accepted",
        proposed_changes={"source_paths": [], "metadata": {}},
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409
    assert "vault_import review has no entity payload" in res.json()["detail"]


def test_apply_vault_import_reapply_updates_sections_without_duplicating():
    review = _seed_review(
        review_type="vault_import",
        target_type="entity",
        current_version="hash-a",
        review_status="accepted",
        proposed_changes=VAULT_IMPORT_PAYLOAD,
    )
    first = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert first.status_code == 200

    second = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert second.status_code == 200
    assert second.json()["already_applied"] is True

    entity = client.get(f"/api/lore/entities/{first.json()['entity_id']}")
    assert len(entity.json()["sections"]) == 1


ASSET_IMPORT_PAYLOAD = {
    "source_path": "Lore/Assets/Images/NPCs/scar.png",
    "source_hash": "hash-scar",
    "asset_type": "image",
    "status": "current",
    "title": "scar",
    "width": 10,
    "height": 20,
    "duplicate_of": None,
}


def test_apply_asset_import_creates_asset_row():
    review = _seed_review(
        review_type="asset_import",
        target_type="asset",
        target_id="",
        base_version="",
        current_version="hash-scar",
        review_status="accepted",
        proposed_changes=ASSET_IMPORT_PAYLOAD,
    )

    applied = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert applied.status_code == 200
    body = applied.json()
    assert body["applied"] is True
    assert body["asset_id"]
    assert body["conflict_with"] is None

    asset = client.get(f"/api/assets/{body['asset_id']}")
    assert asset.status_code == 200
    asset_body = asset.json()
    assert asset_body["source_path"] == "Lore/Assets/Images/NPCs/scar.png"
    assert asset_body["source_hash"] == "hash-scar"
    assert asset_body["status"] == "current"
    assert asset_body["width"] == 10
    assert asset_body["height"] == 20
    assert asset_body["review_status"] == "accepted"
    assert asset_body["freshness_state"] == "fresh"


def test_apply_asset_import_without_asset_payload_returns_409():
    review = _seed_review(
        review_type="asset_import",
        target_type="asset",
        review_status="accepted",
        proposed_changes={},
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409
    assert "asset_import review has no asset payload" in res.json()["detail"]


def test_apply_asset_import_reapply_updates_existing_row():
    review = _seed_review(
        review_type="asset_import",
        target_type="asset",
        review_status="accepted",
        current_version="hash-scar",
        proposed_changes=ASSET_IMPORT_PAYLOAD,
    )
    client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})

    updated_payload = {**ASSET_IMPORT_PAYLOAD, "source_hash": "hash-scar-v2", "width": 99}
    review2 = _seed_review(
        review_type="asset_import",
        target_type="asset",
        review_status="accepted",
        current_version="hash-scar-v2",
        proposed_changes=updated_payload,
    )
    applied2 = client.post(f"/api/sync/reviews/{review2['id']}/apply", json={"confirmation": True})
    assert applied2.status_code == 200

    listed = client.get("/api/assets?q=scar")
    assert len(listed.json()) == 1
    assert listed.json()[0]["source_hash"] == "hash-scar-v2"
    assert listed.json()[0]["width"] == 99


def test_apply_asset_import_sets_conflict_freshness_on_both_rows_when_duplicate():
    existing = client.post(
        "/api/assets", json={"source_path": "Lore/Assets/Images/NPCs/already-registered.png"}
    ).json()

    review = _seed_review(
        review_type="asset_import",
        target_type="asset",
        review_status="accepted",
        current_version="hash-scar",
        conflict_flags=["duplicate_content"],
        proposed_changes={**ASSET_IMPORT_PAYLOAD, "duplicate_of": existing["source_path"]},
    )
    applied = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert applied.status_code == 200
    assert applied.json()["conflict_with"] == existing["source_path"]

    new_asset = client.get(f"/api/assets/{applied.json()['asset_id']}").json()
    assert new_asset["freshness_state"] == "conflict"

    original = client.get(f"/api/assets/{existing['id']}").json()
    assert original["freshness_state"] == "conflict"


def test_apply_asset_import_rejects_invalid_status():
    """Test that _apply_asset_import validates status against ASSET_STATUSES enum."""
    review = _seed_review(
        review_type="asset_import",
        target_type="asset",
        review_status="accepted",
        current_version="hash-invalid-status",
        proposed_changes={**ASSET_IMPORT_PAYLOAD, "status": "bogus"},
    )

    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 422
    assert "status" in res.json()["detail"].lower()


def test_apply_npc_import_updates_stats_and_clears_review():
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO npcs (slug, name, stats, foundry_actor_id_test, foundry_sync_locked)
                VALUES ('hayai', 'Dattoumaru Hayai', %s, 'Actor.pushed1', true)
                RETURNING id
                """,
                (psycopg2.extras.Json({"abilities": {"str": 12}, "naruto_stats": {}}),),
            )
            npc_id = cur.fetchone()["id"]
    finally:
        conn.close()

    review = _seed_review(
        review_type="npc_import",
        target_surface="postgres",
        target_type="npc",
        target_id=str(npc_id),
        proposed_changes={"stats": {"abilities": {"str": 99}, "naruto_stats": {"reputation": 2}}},
        review_status="accepted",
    )

    applied = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"] is True
    assert applied.json()["npc_id"] == str(npc_id)

    npc = client.get("/api/npcs/hayai").json()
    assert npc["stats"]["abilities"]["str"] == 99
    assert npc["stats"]["naruto_stats"]["reputation"] == 2

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM npcs WHERE id = %s", (npc_id,))
    finally:
        conn.close()


def test_apply_npc_import_without_stats_payload_returns_409():
    review = _seed_review(
        review_type="npc_import",
        target_surface="postgres",
        target_type="npc",
        target_id="1",
        review_status="accepted",
        proposed_changes={},
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409
    assert "npc_import review has no stats payload" in res.json()["detail"]


def test_apply_npc_import_for_missing_npc_returns_409():
    review = _seed_review(
        review_type="npc_import",
        target_surface="postgres",
        target_type="npc",
        target_id="99999999",
        review_status="accepted",
        proposed_changes={"stats": {"abilities": {"str": 1}}},
    )
    res = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert res.status_code == 409


def test_apply_npc_import_merges_stats_and_preserves_unrefreshed_keys():
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO npcs (slug, name, stats, foundry_actor_id_test, foundry_sync_locked)
                VALUES ('merge-check', 'Merge Check Npc', %s, 'Actor.pushed2', true)
                RETURNING id
                """,
                (
                    psycopg2.extras.Json(
                        {
                            "classes": {"shinobi": 3},
                            "abilities": {"str": 12},
                            "naruto_stats": {"reputation": 1},
                        }
                    ),
                ),
            )
            npc_id = cur.fetchone()["id"]
    finally:
        conn.close()

    review = _seed_review(
        review_type="npc_import",
        target_surface="postgres",
        target_type="npc",
        target_id=str(npc_id),
        proposed_changes={"stats": {"abilities": {"str": 99}, "naruto_stats": {"reputation": 2}}},
        review_status="accepted",
    )

    applied = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"] is True

    npc = client.get("/api/npcs/merge-check").json()
    # Refreshed keys reflect the new Foundry-fetched values.
    assert npc["stats"]["abilities"]["str"] == 99
    assert npc["stats"]["naruto_stats"]["reputation"] == 2
    # classes was never part of the refresh payload and must survive untouched.
    assert npc["stats"]["classes"] == {"shinobi": 3}

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM npcs WHERE id = %s", (npc_id,))
    finally:
        conn.close()


def test_grouped_reviews_buckets_by_target_type():
    _seed_review(review_type="ticket_import", target_type="ticket", review_status="pending")
    _seed_review(review_type="thread_import", target_type="thread", review_status="conflict")
    _seed_review(review_type="npc_import", target_type="npc", review_status="stale")
    # Not yet applied, so this should also surface under the "ticket" group.
    _seed_review(review_type="ticket_import", target_type="ticket", review_status="accepted")

    res = client.get("/api/sync/reviews/grouped")
    assert res.status_code == 200
    body = res.json()
    by_type = {g["target_type"]: g for g in body["groups"]}
    assert set(by_type) == {"ticket", "thread", "npc"}
    assert by_type["ticket"]["count"] == 2
    assert by_type["thread"]["count"] == 1
    assert by_type["npc"]["count"] == 1
    assert {row["review_type"] for row in by_type["ticket"]["reviews"]} == {"ticket_import"}


def test_grouped_reviews_empty_when_nothing_pending():
    res = client.get("/api/sync/reviews/grouped")
    assert res.status_code == 200
    assert res.json()["groups"] == []


def test_grouped_reviews_includes_accepted_not_yet_applied():
    review = _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        review_status="accepted",
    )

    res = client.get("/api/sync/reviews/grouped")
    assert res.status_code == 200
    by_type = {g["target_type"]: g for g in res.json()["groups"]}
    assert "ticket" in by_type
    assert str(review["id"]) in [row["id"] for row in by_type["ticket"]["reviews"]]


def test_grouped_reviews_excludes_already_applied():
    review = _seed_review(
        review_type="ticket_import",
        target_type="ticket",
        target_id="sync-router-test-ticket",
        review_status="accepted",
        proposed_changes={"ticket": FULL_TICKET_PAYLOAD},
    )

    applied = client.post(f"/api/sync/reviews/{review['id']}/apply", json={"confirmation": True})
    assert applied.status_code == 200

    res = client.get("/api/sync/reviews/grouped")
    assert res.status_code == 200
    by_type = {g["target_type"]: g for g in res.json()["groups"]}
    ticket_ids = [row["id"] for row in by_type.get("ticket", {}).get("reviews", [])]
    assert str(review["id"]) not in ticket_ids


def test_sync_freshness_items_carry_priority():
    _seed_review(review_type="vault_import", target_type="entity", review_status="conflict")
    _seed_review(review_type="thread_import", target_type="thread", review_status="pending")

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sync_jobs (target, direction, status) VALUES ('npc:priority-test', 'foundry_to_postgres', 'failed')"
            )
            cur.execute(
                "INSERT INTO sync_jobs (target, direction, status) VALUES ('npc:blocked-test', 'foundry_to_postgres', 'blocked')"
            )
    finally:
        conn.close()

    res = client.get("/api/sync/freshness")
    assert res.status_code == 200
    items = res.json()["items"]
    by_kind_and_state = {(item["kind"], item["state"]): item["priority"] for item in items}
    assert by_kind_and_state[("review", "conflict")] == "high"
    assert by_kind_and_state[("review", "pending")] == "normal"
    assert by_kind_and_state[("job", "failed")] == "high"
    assert by_kind_and_state[("job", "blocked")] == "high"


def test_sync_freshness_marks_stale_reviews_as_high_priority():
    _seed_review(review_type="vault_import", target_type="entity", review_status="stale")

    res = client.get("/api/sync/freshness")
    assert res.status_code == 200
    items = res.json()["items"]
    by_kind_and_state = {(item["kind"], item["state"]): item["priority"] for item in items}
    assert by_kind_and_state[("review", "stale")] == "high"


def test_sync_freshness_breaks_down_stale_counts_by_category():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lore_sources (source_path, title, freshness_state)
                VALUES ('Lore/stale-vault-test.md', 'Stale Vault Test', 'stale_source_changed')
                """
            )
            cur.execute(
                """
                INSERT INTO lore_assets (source_path, title, freshness_state, mirror_state)
                VALUES ('Lore/Assets/stale-asset-test.png', 'Stale Asset Test', 'stale_source_changed', 'fresh')
                """
            )
            cur.execute(
                """
                INSERT INTO lore_assets (source_path, title, freshness_state, mirror_state)
                VALUES ('Lore/Assets/stale-foundry-test.png', 'Stale Foundry Test', 'fresh', 'stale_mirror')
                """
            )
    finally:
        conn.close()

    res = client.get("/api/sync/freshness")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "stale"
    assert data["counts"]["stale_vault"] == 1
    assert data["counts"]["stale_asset"] == 1
    assert data["counts"]["stale_foundry"] == 1

    by_kind_and_id = {(item["kind"], item["id"]): item for item in data["items"]}
    assert by_kind_and_id[("state", "stale-vault")]["priority"] == "high"
    assert by_kind_and_id[("state", "stale-asset")]["priority"] == "high"
    assert by_kind_and_id[("state", "stale-foundry")]["priority"] == "high"


def test_sync_freshness_surfaces_unconfigured_foundry_integration(monkeypatch):
    from gm_dashboard import sync_router

    monkeypatch.setattr(
        sync_router,
        "_foundry_integration_state",
        lambda: {"state": "unconfigured", "path": "fake/.env"},
    )

    res = client.get("/api/sync/freshness")
    assert res.status_code == 200
    data = res.json()
    assert data["counts"]["unconfigured_integrations"] == 1

    by_kind_and_id = {(item["kind"], item["id"]): item for item in data["items"]}
    integration_item = by_kind_and_id[("integration", "foundry-unconfigured")]
    assert integration_item["priority"] == "high"
    assert integration_item["state"] == "unconfigured"
