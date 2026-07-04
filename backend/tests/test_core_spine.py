from __future__ import annotations

import os
from datetime import UTC, datetime

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
        cur.execute("DELETE FROM session_notes")
        cur.execute("DELETE FROM scenes")
        cur.execute("DELETE FROM sessions")
        cur.execute("DELETE FROM threads")
        cur.execute("DELETE FROM lore_assets")
        cur.execute("DELETE FROM lore_relationships")
        cur.execute("DELETE FROM lore_aliases")
        cur.execute("DELETE FROM lore_sections")
        cur.execute("DELETE FROM lore_entities")
        cur.execute("DELETE FROM lore_sources")
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
    conn.close()


def test_lore_spine_accepts_source_entity_section_alias_asset_and_relationship():
    _clean()
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_sources (source_path, source_hash, title, review_status)
                VALUES ('Lore/NPCs/Haiiro.md', 'hash-a', 'Haiiro', 'accepted')
                RETURNING id, visibility, freshness_state
                """
            )
            source = cur.fetchone()

            cur.execute(
                """
                INSERT INTO lore_entities (
                  slug, title, entity_type, primary_source_id, source_path, review_status
                )
                VALUES (
                  'kaguya-haiiro', 'Kaguya Haiiro', 'npc', %(source_id)s,
                  'Lore/NPCs/Haiiro.md', 'accepted'
                )
                RETURNING id, graph_endpoint_id, visibility, freshness_state
                """,
                {"source_id": source["id"]},
            )
            entity = cur.fetchone()

            cur.execute(
                """
                INSERT INTO lore_sections (source_id, entity_id, heading, body, section_order)
                VALUES (%(source_id)s, %(entity_id)s, 'Profile', 'Missing in forest.', 1)
                RETURNING id
                """,
                {"source_id": source["id"], "entity_id": entity["id"]},
            )
            section = cur.fetchone()

            cur.execute(
                """
                INSERT INTO lore_aliases (entity_id, alias)
                VALUES (%(entity_id)s, 'Haiiro')
                RETURNING id
                """,
                {"entity_id": entity["id"]},
            )
            alias = cur.fetchone()

            cur.execute(
                """
                INSERT INTO lore_assets (source_path, title, linked_entity_id, review_status)
                VALUES ('Assets/NPCs/haiiro.png', 'Haiiro portrait', %(entity_id)s, 'accepted')
                RETURNING id, graph_endpoint_id, mirror_state
                """,
                {"entity_id": entity["id"]},
            )
            asset = cur.fetchone()

            cur.execute(
                """
                INSERT INTO lore_relationships (
                  source_type, source_id, target_type, target_id,
                  relationship_type, provenance, review_status
                )
                VALUES (
                  'entity', %(entity_id)s, 'asset', %(asset_id)s,
                  'uses_asset', 'manual', 'accepted'
                )
                RETURNING id, direction, visibility
                """,
                {"entity_id": str(entity["id"]), "asset_id": str(asset["id"])},
            )
            relationship = cur.fetchone()

            assert source["visibility"] == "gm"
            assert entity["graph_endpoint_id"] == f"entity:{entity['id']}"
            assert entity["freshness_state"] == "unknown"
            assert section["id"]
            assert alias["id"]
            assert asset["graph_endpoint_id"] == f"asset:{asset['id']}"
            assert asset["mirror_state"] == "not_mirrored"
            assert relationship["direction"] == "directed"
            assert relationship["visibility"] == "gm"
    finally:
        conn.close()
        _clean()


def test_sync_job_links_to_review_and_keeps_payloads_separate():
    _clean()
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  proposed_changes
                )
                VALUES (
                  'vault_import', 'vault', 'postgres', 'entity', 'kaguya-haiiro',
                  '{"field": "summary"}'::jsonb
                )
                RETURNING id
                """
            )
            review_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO sync_jobs (
                  target, direction, status, job_type, source_surface, target_surface,
                  review_id, input_payload, result_payload, error_code, error_message
                )
                VALUES (
                  'entity:kaguya-haiiro', 'vault_to_postgres', 'succeeded',
                  'apply_review', 'vault', 'postgres', %(review_id)s,
                  '{"review_id": "linked"}'::jsonb, '{"updated": 1}'::jsonb, '', ''
                )
                RETURNING review_id, input_payload, result_payload
                """,
                {"review_id": review_id},
            )
            job = cur.fetchone()

            assert job["review_id"] == review_id
            assert job["input_payload"]["review_id"] == "linked"
            assert job["result_payload"]["updated"] == 1
    finally:
        conn.close()
        _clean()


def _seed_source() -> str:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_sources (source_path, source_hash, title, review_status, freshness_state)
                VALUES ('Lore/NPCs/Haiiro.md', 'hash-a', 'Haiiro', 'accepted', 'fresh')
                RETURNING id
                """
            )
            return str(cur.fetchone()["id"])
    finally:
        conn.close()


def test_lore_source_api_filters_patches_and_composes_children():
    _clean()
    try:
        created = client.post(
            "/api/lore/sources",
            json={
                "source_path": "Lore/Locations/Iron Keep.md",
                "source_hash": "hash-a",
                "title": "Iron Keep",
                "visibility": "mixed",
                "freshness_state": "fresh",
                "review_status": "accepted",
                "metadata": {"registry": "Lore_Registry"},
            },
        )
        assert created.status_code == 201
        source = created.json()
        assert source["source_surface"] == "vault"
        assert source["metadata"]["registry"] == "Lore_Registry"

        duplicate = client.post(
            "/api/lore/sources",
            json={"source_path": "Lore/Locations/Iron Keep.md"},
        )
        assert duplicate.status_code == 409

        entity = client.post(
            "/api/lore/entities",
            json={
                "slug": "iron-keep",
                "title": "Iron Keep",
                "entity_type": "location",
                "primary_source_id": source["id"],
                "source_path": "Lore/Locations/Iron Keep.md",
            },
        )
        assert entity.status_code == 201

        section = client.post(
            f"/api/lore/entities/{entity.json()['id']}/sections",
            json={
                "source_id": source["id"],
                "heading": "Overview",
                "body": "A fortified border keep.",
                "section_order": 1,
            },
        )
        assert section.status_code == 201

        patched = client.patch(
            f"/api/lore/sources/{source['id']}",
            json={"freshness_state": "stale_source_changed", "source_hash": "hash-b"},
        )
        assert patched.status_code == 200
        assert patched.json()["freshness_state"] == "stale_source_changed"
        assert patched.json()["source_hash"] == "hash-b"

        listed = client.get("/api/lore/sources?freshness_state=stale_source_changed&q=iron")
        assert listed.status_code == 200
        assert [row["source_path"] for row in listed.json()] == ["Lore/Locations/Iron Keep.md"]

        detail = client.get(f"/api/lore/sources/{source['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["entities"][0]["slug"] == "iron-keep"
        assert body["sections"][0]["heading"] == "Overview"
    finally:
        _clean()


def test_lore_section_api_filters_and_patches_prose_annexes():
    _clean()
    source_id = _seed_source()
    try:
        entity = client.post(
            "/api/lore/entities",
            json={
                "slug": "haiiro-section-test",
                "title": "Haiiro Section Test",
                "entity_type": "npc",
                "primary_source_id": source_id,
            },
        )
        assert entity.status_code == 201
        entity_id = entity.json()["id"]

        section = client.post(
            f"/api/lore/entities/{entity_id}/sections",
            json={
                "source_id": source_id,
                "heading": "Signals",
                "body": "Old body.",
                "section_order": 2,
                "heading_path": ["Profile", "Signals"],
                "freshness_state": "fresh",
            },
        )
        assert section.status_code == 201
        section_id = section.json()["id"]

        patched = client.patch(
            f"/api/lore/sections/{section_id}",
            json={
                "body": "Updated body for reviewed projection.",
                "section_order": 1,
                "freshness_state": "stale_db_newer",
                "metadata": {"projection": "manual-test"},
            },
        )
        assert patched.status_code == 200
        patched_body = patched.json()
        assert patched_body["body"] == "Updated body for reviewed projection."
        assert patched_body["section_order"] == 1
        assert patched_body["metadata"]["projection"] == "manual-test"

        detail = client.get(f"/api/lore/sections/{section_id}")
        assert detail.status_code == 200
        assert detail.json()["heading_path"] == ["Profile", "Signals"]

        listed = client.get(
            f"/api/lore/sections?source_id={source_id}&freshness_state=stale_db_newer&q=projection"
        )
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [section_id]

        invalid = client.patch(
            f"/api/lore/sections/{section_id}",
            json={"visibility": "public"},
        )
        assert invalid.status_code == 422
    finally:
        _clean()


def test_lore_alias_api_filters_patches_and_rejects_duplicates():
    _clean()
    try:
        entity = client.post(
            "/api/lore/entities",
            json={"slug": "kaguya-haiiro", "title": "Kaguya Haiiro", "entity_type": "npc"},
        )
        assert entity.status_code == 201
        entity_id = entity.json()["id"]

        alias = client.post(
            f"/api/lore/entities/{entity_id}/aliases",
            json={"alias": "Haiiro", "alias_kind": "short-name", "locale": "pt-BR"},
        )
        assert alias.status_code == 201
        alias_id = alias.json()["id"]

        patched = client.patch(
            f"/api/lore/aliases/{alias_id}",
            json={"alias": "Haiiro-sama", "review_status": "merged"},
        )
        assert patched.status_code == 200
        assert patched.json()["alias"] == "Haiiro-sama"
        assert patched.json()["review_status"] == "merged"

        detail = client.get(f"/api/lore/aliases/{alias_id}")
        assert detail.status_code == 200
        assert detail.json()["locale"] == "pt-BR"

        listed = client.get(f"/api/lore/aliases?entity_id={entity_id}&q=sama")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [alias_id]

        duplicate = client.post(
            f"/api/lore/entities/{entity_id}/aliases",
            json={"alias": "Haiiro-sama", "alias_kind": "short-name"},
        )
        assert duplicate.status_code == 409

        invalid = client.patch(
            f"/api/lore/aliases/{alias_id}",
            json={"review_status": "done"},
        )
        assert invalid.status_code == 422
    finally:
        _clean()


def test_lore_entity_api_composes_aliases_sections_relationships_and_assets():
    _clean()
    source_id = _seed_source()
    try:
        created = client.post(
            "/api/lore/entities",
            json={
                "slug": "kaguya-haiiro",
                "title": "Kaguya Haiiro",
                "entity_type": "npc",
                "summary": "Missing scout.",
                "primary_source_id": source_id,
                "source_path": "Lore/NPCs/Haiiro.md",
                "visibility": "gm",
                "freshness_state": "fresh",
            },
        )
        assert created.status_code == 201
        entity = created.json()
        assert entity["graph_endpoint_id"] == f"entity:{entity['id']}"

        alias = client.post(
            f"/api/lore/entities/{entity['id']}/aliases",
            json={"alias": "Haiiro"},
        )
        assert alias.status_code == 201

        section = client.post(
            f"/api/lore/entities/{entity['id']}/sections",
            json={
                "source_id": source_id,
                "heading": "Profile",
                "body": "Missing in forest.",
                "section_order": 1,
                "freshness_state": "fresh",
            },
        )
        assert section.status_code == 201

        asset = client.post(
            "/api/assets",
            json={
                "source_path": "Assets/NPCs/haiiro.png",
                "title": "Haiiro portrait",
                "linked_entity_id": entity["id"],
                "freshness_state": "fresh",
            },
        )
        assert asset.status_code == 201
        asset_body = asset.json()
        assert asset_body["graph_endpoint_id"] == f"asset:{asset_body['id']}"

        relationship = client.post(
            "/api/relationships",
            json={
                "source_type": "entity",
                "source_id": entity["graph_endpoint_id"],
                "target_type": "asset",
                "target_id": asset_body["graph_endpoint_id"],
                "relationship_type": "uses_asset",
                "freshness_state": "fresh",
            },
        )
        assert relationship.status_code == 201

        detail = client.get(f"/api/lore/entities/{entity['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["title"] == "Kaguya Haiiro"
        assert body["aliases"][0]["alias"] == "Haiiro"
        assert body["sections"][0]["heading"] == "Profile"
        assert body["relationships"][0]["relationship_type"] == "uses_asset"
        assert body["assets"][0]["source_path"] == "Assets/NPCs/haiiro.png"

        listed = client.get("/api/lore/entities?entity_type=npc&q=haiiro")
        assert listed.status_code == 200
        assert [row["slug"] for row in listed.json()] == ["kaguya-haiiro"]
    finally:
        _clean()


def test_relationship_and_asset_patch_routes():
    _clean()
    try:
        entity = client.post(
            "/api/lore/entities",
            json={"slug": "iron-keep", "title": "Iron Keep", "entity_type": "location"},
        ).json()
        rel = client.post(
            "/api/relationships",
            json={
                "source_type": "scene",
                "source_id": "12",
                "target_type": "entity",
                "target_id": entity["id"],
                "relationship_type": "located_at",
            },
        )
        assert rel.status_code == 201
        assert rel.json()["source_id"] == "scene:12"
        assert rel.json()["target_id"] == entity["graph_endpoint_id"]

        patched_rel = client.patch(
            f"/api/relationships/{rel.json()['id']}",
            json={"review_status": "accepted", "context": "Council scene."},
        )
        assert patched_rel.status_code == 200
        assert patched_rel.json()["context"] == "Council scene."

        relationships = client.get("/api/relationships?source_type=scene&source_id=scene:12")
        assert relationships.status_code == 200
        assert len(relationships.json()) == 1

        invalid_endpoint = client.post(
            "/api/relationships",
            json={
                "source_type": "scene",
                "source_id": "entity:not-a-scene",
                "target_type": "entity",
                "target_id": entity["graph_endpoint_id"],
                "relationship_type": "located_at",
            },
        )
        assert invalid_endpoint.status_code == 422

        asset = client.post(
            "/api/assets",
            json={"source_path": "Assets/Maps/iron-keep.webp", "title": "Iron Keep map"},
        )
        assert asset.status_code == 201
        patched_asset = client.patch(
            f"/api/assets/{asset.json()['id']}",
            json={"mirror_state": "mirrored", "foundry_path": "worlds/kaihou/iron-keep.webp"},
        )
        assert patched_asset.status_code == 200
        assert patched_asset.json()["mirror_state"] == "mirrored"

        mirrored = client.get("/api/assets?mirror_state=mirrored&q=iron")
        assert mirrored.status_code == 200
        assert mirrored.json()[0]["source_path"] == "Assets/Maps/iron-keep.webp"
    finally:
        _clean()


def test_relationship_filters_normalize_raw_endpoint_ids():
    _clean()
    try:
        rel = client.post(
            "/api/relationships",
            json={
                "source_type": "scene",
                "source_id": "42",
                "target_type": "thread",
                "target_id": "shadowlands-pressure",
                "relationship_type": "advances",
            },
        )
        assert rel.status_code == 201
        assert rel.json()["source_id"] == "scene:42"
        assert rel.json()["target_id"] == "thread:shadowlands-pressure"

        by_raw_source = client.get("/api/relationships?source_type=scene&source_id=42")
        assert by_raw_source.status_code == 200
        assert [row["id"] for row in by_raw_source.json()] == [rel.json()["id"]]

        by_raw_target = client.get(
            "/api/relationships?target_type=thread&target_id=shadowlands-pressure"
        )
        assert by_raw_target.status_code == 200
        assert [row["id"] for row in by_raw_target.json()] == [rel.json()["id"]]

        invalid = client.get("/api/relationships?source_type=scene&source_id=thread:wrong")
        assert invalid.status_code == 422
    finally:
        _clean()


def test_relationship_review_stages_then_applies_graph_edges():
    _clean()
    try:
        entity = client.post(
            "/api/lore/entities",
            json={"slug": "iron-keep", "title": "Iron Keep", "entity_type": "location"},
        ).json()

        review = client.post(
            "/api/relationships/review",
            json={
                "source_surface": "manual",
                "target_surface": "postgres",
                "relationships": [
                    {
                        "source_type": "thread",
                        "source_id": "training-arc-pressure",
                        "target_type": "entity",
                        "target_id": entity["id"],
                        "relationship_type": "foreshadows",
                        "provenance": "ai_suggestion",
                        "confidence": 0.73,
                        "context": "Pressure thread points toward the keep.",
                    }
                ],
            },
        )
        assert review.status_code == 201
        review_body = review.json()
        assert review_body["review_type"] == "relationship_change"
        assert review_body["target_type"] == "relationship"
        assert review_body["review_status"] == "pending"
        staged = review_body["proposed_changes"]["relationships"][0]
        assert staged["source_id"] == "thread:training-arc-pressure"
        assert staged["target_id"] == entity["graph_endpoint_id"]

        before_apply = client.get(
            f"/api/relationships?source_type=thread&source_id={staged['source_id']}"
        )
        assert before_apply.status_code == 200
        assert before_apply.json() == []

        decided = client.patch(
            f"/api/sync/reviews/{review_body['id']}",
            json={"review_status": "accepted", "decision": {"accepted_all": True}},
        )
        assert decided.status_code == 200

        applied = client.post(
            f"/api/sync/reviews/{review_body['id']}/apply",
            json={"confirmation": True},
        )
        assert applied.status_code == 200
        assert applied.json()["applied"] is True
        assert len(applied.json()["relationship_ids"]) == 1

        relationships = client.get(
            f"/api/relationships?source_type=thread&source_id={staged['source_id']}"
        )
        assert relationships.status_code == 200
        assert relationships.json()[0]["relationship_type"] == "foreshadows"
        assert relationships.json()[0]["review_status"] == "accepted"

        review_detail = client.get(f"/api/sync/reviews/{review_body['id']}")
        assert review_detail.status_code == 200
        assert review_detail.json()["applied_at"] is not None
    finally:
        _clean()


def test_lore_import_review_alias_stages_vault_import_in_sync_reviews():
    _clean()
    try:
        review = client.post(
            "/api/lore/import/review",
            json={
                "target_type": "entity",
                "target_id": "entity:kaguya-haiiro",
                "base_version": "hash-a",
                "current_version": "hash-b",
                "source_paths": ["Lore/NPCs/Haiiro.md"],
                "proposed_changes": {"entity": {"slug": "kaguya-haiiro"}},
                "metadata": {"importer": "test"},
            },
        )
        assert review.status_code == 201
        body = review.json()
        assert body["review_type"] == "vault_import"
        assert body["source_surface"] == "vault"
        assert body["target_surface"] == "postgres"
        assert body["review_status"] == "pending"
        assert body["proposed_changes"]["source_paths"] == ["Lore/NPCs/Haiiro.md"]
        assert body["proposed_changes"]["entity"]["slug"] == "kaguya-haiiro"

        listed = client.get("/api/sync/reviews?review_type=vault_import&target_type=entity")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [body["id"]]

        invalid = client.post(
            "/api/lore/import/review",
            json={"target_type": "downtime_action"},
        )
        assert invalid.status_code == 422
    finally:
        _clean()


def test_lore_import_apply_alias_uses_generic_sync_review_apply_path():
    _clean()
    try:
        review = client.post(
            "/api/lore/import/review",
            json={"target_type": "entity", "target_id": "entity:kaguya-haiiro"},
        )
        assert review.status_code == 201
        review_id = review.json()["id"]

        unconfirmed = client.post(f"/api/lore/import/{review_id}/apply", json={})
        assert unconfirmed.status_code == 422

        decided = client.patch(
            f"/api/sync/reviews/{review_id}",
            json={"review_status": "accepted", "decision": {"accepted_all": True}},
        )
        assert decided.status_code == 200

        unsupported = client.post(
            f"/api/lore/import/{review_id}/apply",
            json={"confirmation": True},
        )
        assert unsupported.status_code == 409
        assert "review_type=vault_import" in unsupported.json()["detail"]

        freshness = client.get("/api/sync/freshness")
        assert freshness.status_code == 200
        assert freshness.json()["counts"]["blocked_jobs"] == 1
    finally:
        _clean()


def test_review_apply_is_auditable_and_repeat_apply_returns_existing_job():
    _clean()
    try:
        review = client.post(
            "/api/relationships/review",
            json={
                "relationships": [
                    {
                        "source_type": "thread",
                        "source_id": "shadowlands-pressure",
                        "target_type": "scene",
                        "target_id": "council-scene",
                        "relationship_type": "foreshadows",
                    }
                ],
            },
        )
        assert review.status_code == 201
        review_id = review.json()["id"]

        decided = client.patch(
            f"/api/sync/reviews/{review_id}",
            json={"review_status": "accepted", "decision": {"accepted_all": True}},
        )
        assert decided.status_code == 200

        first_apply = client.post(
            f"/api/sync/reviews/{review_id}/apply",
            json={"confirmation": True},
        )
        assert first_apply.status_code == 200
        first_body = first_apply.json()
        assert first_body["applied"] is True
        assert first_body["sync_job_id"]
        assert first_body["relationship_ids"]

        job = client.get(f"/api/sync/jobs/{first_body['sync_job_id']}")
        assert job.status_code == 200
        job_body = job.json()
        assert job_body["job_type"] == "apply_review"
        assert job_body["review_id"] == review_id
        assert job_body["status"] == "succeeded"
        assert job_body["input_payload"]["review_id"] == review_id
        assert job_body["result_payload"]["relationship_ids"] == first_body["relationship_ids"]

        repeat_apply = client.post(
            f"/api/sync/reviews/{review_id}/apply",
            json={"confirmation": True},
        )
        assert repeat_apply.status_code == 200
        repeat_body = repeat_apply.json()
        assert repeat_body["applied"] is True
        assert repeat_body["already_applied"] is True
        assert repeat_body["sync_job_id"] == first_body["sync_job_id"]
        assert repeat_body["relationship_ids"] == first_body["relationship_ids"]

        relationships = client.get("/api/relationships?source_type=thread&source_id=thread:shadowlands-pressure")
        assert relationships.status_code == 200
        assert len(relationships.json()) == 1
    finally:
        _clean()


def test_core_spine_database_constraints_guard_shared_states():
    _clean()
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sync_jobs (target, direction)
                VALUES ('entity:constraint-test', 'manual_to_postgres')
                RETURNING status
                """
            )
            assert cur.fetchone()["status"] == "queued"

            with pytest.raises(psycopg2.errors.CheckViolation):
                cur.execute(
                    """
                    INSERT INTO sync_reviews (
                      review_type, source_surface, target_surface, target_type, review_status
                    )
                    VALUES ('vault_import', 'bad_surface', 'postgres', 'entity', 'pending')
                    """
                )

            with pytest.raises(psycopg2.errors.CheckViolation):
                cur.execute(
                    """
                    INSERT INTO lore_relationships (
                      source_type, source_id, target_type, target_id, relationship_type
                    )
                    VALUES ('bad_type', 'bad:1', 'entity', 'entity:1', 'mentions')
                    """
                )

            with pytest.raises(psycopg2.errors.CheckViolation):
                cur.execute(
                    """
                    INSERT INTO scenes (title, placement)
                    VALUES ('Bad placement', 'sideboard')
                    """
                )
    finally:
        conn.close()
        _clean()


def test_sync_freshness_summarizes_reviews_jobs_and_stale_records():
    _clean()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lore_entities (slug, title, entity_type, freshness_state)
                VALUES ('stale-entity', 'Stale Entity', 'article', 'stale_source_changed')
                """
            )
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id, review_status
                )
                VALUES ('vault_import', 'vault', 'postgres', 'entity', 'stale-entity', 'pending')
                """
            )
            cur.execute(
                """
                INSERT INTO sync_jobs (
                  target, direction, status, job_type, source_surface, target_surface,
                  error_code, error_message
                )
                VALUES (
                  'entity:stale-entity', 'vault_to_postgres', 'failed', 'apply_review',
                  'vault', 'postgres', 'boom', 'Failed for test.'
                )
                """
            )

        res = client.get("/api/sync/freshness")
        assert res.status_code == 200
        data = res.json()
        assert data["state"] == "failed"
        assert data["counts"]["pending_reviews"] == 1
        assert data["counts"]["failed_jobs"] == 1
        assert data["counts"]["stale_records"] >= 1
        assert {item["kind"] for item in data["items"]} == {"review", "job"}
    finally:
        conn.close()
        _clean()


def test_graph_endpoint_ids_support_thread_session_scene_relationships():
    _clean()
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO threads (id, title, status, freshness_state)
                VALUES ('shadowlands-pressure', 'Shadowlands Pressure', 'active', 'fresh')
                RETURNING id, graph_endpoint_id
                """
            )
            thread = cur.fetchone()

        session_res = client.post(
            "/api/sessions",
            json={"number": 991, "name": "Graph endpoint test", "status": "Planned"},
        )
        assert session_res.status_code == 201
        session = session_res.json()
        assert session["graph_endpoint_id"] == f"session:{session['id']}"
        assert session["status"] == "planned"

        scene_res = client.post(
            "/api/scenes",
            json={
                "title": "Council pressure",
                "session_id": session["id"],
                "purpose": "Tie pressure to the active thread.",
            },
        )
        assert scene_res.status_code == 201
        scene = scene_res.json()
        assert scene["graph_endpoint_id"] == f"scene:{scene['id']}"

        assert thread["graph_endpoint_id"] == "thread:shadowlands-pressure"

        thread_scene = client.post(
            "/api/relationships",
            json={
                "source_type": "thread",
                "source_id": thread["graph_endpoint_id"],
                "target_type": "scene",
                "target_id": scene["graph_endpoint_id"],
                "relationship_type": "foreshadows",
                "freshness_state": "fresh",
            },
        )
        assert thread_scene.status_code == 201

        session_scene = client.post(
            "/api/relationships",
            json={
                "source_type": "session",
                "source_id": session["graph_endpoint_id"],
                "target_type": "scene",
                "target_id": scene["graph_endpoint_id"],
                "relationship_type": "appears_in",
                "freshness_state": "fresh",
            },
        )
        assert session_scene.status_code == 201

        relationships = client.get(
            f"/api/relationships?target_type=scene&target_id={scene['graph_endpoint_id']}"
        )
        assert relationships.status_code == 200
        assert {row["source_type"] for row in relationships.json()} == {"thread", "session"}
    finally:
        conn.close()
        _clean()


def test_thread_api_is_db_backed_and_filterable():
    _clean()
    try:
        created = client.post(
            "/api/threads",
            json={
                "id": "shadowlands-pressure",
                "title": "Shadowlands Pressure",
                "status": "active",
                "priority": "high",
                "arc": "Training Arc",
                "theme": "Survival pressure",
                "pressure": "The forest keeps escalating.",
                "stakes": "Haiiro may be lost.",
                "next_move": "Put a hard choice at the treeline.",
                "clock_label": "Forest closes in",
                "clock_value": 2,
                "clock_max": 6,
                "unresolved_questions": ["Where is Haiiro?"],
                "freshness_state": "fresh",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["graph_endpoint_id"] == "thread:shadowlands-pressure"
        assert body["unresolved_questions"] == ["Where is Haiiro?"]

        duplicate = client.post(
            "/api/threads",
            json={"id": "shadowlands-pressure", "title": "Duplicate"},
        )
        assert duplicate.status_code == 409

        patched = client.patch(
            "/api/threads/shadowlands-pressure",
            json={
                "pressure": "The patrol beacon forces movement.",
                "freshness_state": "stale_db_newer",
                "review_status": "merged",
            },
        )
        assert patched.status_code == 200
        assert patched.json()["pressure"] == "The patrol beacon forces movement."
        assert patched.json()["review_status"] == "merged"

        detail = client.get("/api/threads/shadowlands-pressure")
        assert detail.status_code == 200
        assert detail.json()["stakes"] == "Haiiro may be lost."

        listed = client.get("/api/threads?status=active&arc=Training%20Arc&q=beacon")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == ["shadowlands-pressure"]
    finally:
        _clean()


def test_thread_api_validates_shared_states():
    _clean()
    try:
        invalid = client.post(
            "/api/threads",
            json={
                "id": "bad-thread",
                "title": "Bad Thread",
                "priority": "immediate",
                "freshness_state": "made_up",
            },
        )
        assert invalid.status_code == 422
    finally:
        _clean()


def test_thread_summary_and_detail_compose_linked_entities_sessions_and_scenes():
    _clean()
    try:
        source_id = _seed_source()
        entity = client.post(
            "/api/lore/entities",
            json={
                "slug": "iron-keep-thread-detail",
                "title": "Iron Keep Thread Detail",
                "entity_type": "location",
                "primary_source_id": source_id,
            },
        )
        assert entity.status_code == 201
        entity_body = entity.json()

        session = client.post(
            "/api/sessions",
            json={"number": 99, "name": "Thread Detail Session", "status": "Planned"},
        )
        assert session.status_code == 201
        session_body = session.json()

        scene = client.post(
            "/api/scenes",
            json={
                "title": "Thread Detail Scene",
                "status": "Draft",
                "session_id": session_body["id"],
                "purpose": "Force a direction choice.",
            },
        )
        assert scene.status_code == 201
        scene_body = scene.json()

        thread = client.post(
            "/api/threads",
            json={
                "id": "thread-detail-test",
                "title": "Thread Detail Test",
                "status": "active",
                "priority": "urgent",
                "next_move": "Frame the Iron Keep choice.",
                "sessions": [99],
                "last_touched_at": datetime.now(UTC).isoformat(),
                "freshness_state": "fresh",
            },
        )
        assert thread.status_code == 201

        rel_entity = client.post(
            "/api/relationships",
            json={
                "source_type": "thread",
                "source_id": "thread-detail-test",
                "target_type": "entity",
                "target_id": entity_body["graph_endpoint_id"],
                "relationship_type": "points_to",
            },
        )
        assert rel_entity.status_code == 201
        rel_scene = client.post(
            "/api/relationships",
            json={
                "source_type": "scene",
                "source_id": str(scene_body["id"]),
                "target_type": "thread",
                "target_id": "thread-detail-test",
                "relationship_type": "advances",
            },
        )
        assert rel_scene.status_code == 201

        summary = client.get("/api/threads/summary")
        assert summary.status_code == 200
        assert summary.json()["active"] == 1
        assert summary.json()["high_priority"] == 1
        assert summary.json()["next_moves"][0]["id"] == "thread-detail-test"
        assert summary.json()["next_campaign_move"]["id"] == "thread-detail-test"

        cockpit = client.get("/api/cockpit/thread-direction")
        assert cockpit.status_code == 200
        assert cockpit.json()["next_campaign_move"]["next_move"] == "Frame the Iron Keep choice."
        assert cockpit.json()["active_pressure"][0]["id"] == "thread-detail-test"

        detail = client.get("/api/threads/thread-detail-test")
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["stale_state"]["state"] == "current"
        assert detail_body["linked"]["entities"][0]["slug"] == "iron-keep-thread-detail"
        assert detail_body["linked"]["sessions"][0]["number"] == 99
        assert detail_body["linked"]["scenes"][0]["title"] == "Thread Detail Scene"
        assert {row["relationship_type"] for row in detail_body["linked"]["relationships"]} == {
            "points_to",
            "advances",
        }
    finally:
        _clean()


def test_thread_import_review_applies_legacy_thread_payload():
    _clean()
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  current_version, proposed_changes
                )
                VALUES (
                  'thread_import', 'vault', 'postgres', 'thread', 'legacy-thread-test',
                  'sha256:legacy',
                  %(proposed_changes)s
                )
                RETURNING id
                """,
                {
                    "proposed_changes": psycopg2.extras.Json(
                        {
                            "action": "import_thread",
                            "thread": {
                                "id": "legacy-thread-test",
                                "title": "Legacy Thread Test",
                                "status": "active",
                                "priority": "high",
                                "arc": None,
                                "theme": "",
                                "pressure": "",
                                "stakes": "",
                                "next_move": "Make the imported thread visible.",
                                "clock_label": None,
                                "clock_value": None,
                                "clock_max": None,
                                "unresolved_questions": [],
                                "last_touched_at": None,
                                "visibility": "gm",
                                "freshness_state": "fresh",
                                "review_status": "pending",
                                "factions": ["Kaguya Haiiro"],
                                "sessions": [17],
                                "vault_path": "Campaign Management/authorial/threads/legacy-thread-test.md",
                                "body": "# Legacy Thread Test",
                            },
                            "source_preserved": True,
                        }
                    )
                },
            )
            review_id = str(cur.fetchone()["id"])

        accepted = client.patch(
            f"/api/sync/reviews/{review_id}",
            json={"review_status": "accepted", "decision": {"note": "test apply"}},
        )
        assert accepted.status_code == 200

        applied = client.post(
            f"/api/sync/reviews/{review_id}/apply",
            json={"confirmation": True},
        )
        assert applied.status_code == 200
        assert applied.json()["thread_id"] == "legacy-thread-test"
        assert applied.json()["source_files_deleted"] == 0

        detail = client.get("/api/threads/legacy-thread-test")
        assert detail.status_code == 200
        body = detail.json()
        assert body["title"] == "Legacy Thread Test"
        assert body["next_move"] == "Make the imported thread visible."
        assert body["sessions"] == [17]
    finally:
        conn.close()
        _clean()


def test_system_enum_catalog_matches_spine_contract_values():
    res = client.get("/api/system/enums")
    assert res.status_code == 200
    data = res.json()

    assert data["review_statuses"] == [
        "accepted",
        "conflict",
        "deferred",
        "merged",
        "pending",
        "rejected",
        "stale",
    ]
    assert data["freshness_states"] == [
        "conflict",
        "fresh",
        "missing_mirror",
        "missing_source",
        "stale_db_newer",
        "stale_source_changed",
        "unknown",
    ]
    assert data["legacy_session_statuses"] == ["Active", "Planned", "Played"]
    assert data["graph_endpoint_types"] == ["asset", "entity", "scene", "session", "thread"]
    assert data["scene_placements"] == ["backlog", "floating", "ordered"]
    assert data["session_statuses"] == ["archived", "cancelled", "planned", "played", "ready"]
