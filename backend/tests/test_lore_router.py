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
        cur.execute("DELETE FROM lore_assets")
        cur.execute("DELETE FROM lore_relationships")
        cur.execute("DELETE FROM lore_aliases")
        cur.execute("DELETE FROM lore_sections")
        cur.execute("DELETE FROM lore_entities")
        cur.execute("DELETE FROM lore_sources")
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
    conn.close()


@pytest.fixture(autouse=True)
def clean_lore_tables():
    _clean()
    yield
    _clean()


NIL_UUID = "00000000-0000-0000-0000-000000000000"


# ---- lore/sources -----------------------------------------------------


def test_create_source_rejects_invalid_enum_fields():
    bad_surface = client.post(
        "/api/lore/sources",
        json={"source_path": "Lore/x.md", "source_surface": "made_up"},
    )
    assert bad_surface.status_code == 422

    bad_visibility = client.post(
        "/api/lore/sources",
        json={"source_path": "Lore/y.md", "visibility": "made_up"},
    )
    assert bad_visibility.status_code == 422


def test_get_and_patch_source_404_for_unknown_id():
    assert client.get(f"/api/lore/sources/{NIL_UUID}").status_code == 404
    assert client.patch(f"/api/lore/sources/{NIL_UUID}", json={"title": "x"}).status_code == 404


def test_list_sources_filters_by_surface_and_kind():
    client.post(
        "/api/lore/sources",
        json={"source_path": "Lore/a.md", "source_kind": "markdown", "source_surface": "vault"},
    )
    client.post(
        "/api/lore/sources",
        json={"source_path": "Lore/b.pdf", "source_kind": "pdf", "source_surface": "vault"},
    )

    by_kind = client.get("/api/lore/sources?source_kind=pdf")
    assert by_kind.status_code == 200
    assert [row["source_path"] for row in by_kind.json()] == ["Lore/b.pdf"]

    by_surface = client.get("/api/lore/sources?source_surface=vault")
    assert by_surface.status_code == 200
    assert len(by_surface.json()) == 2


# ---- lore/entities ------------------------------------------------------


def test_create_entity_rejects_invalid_enum_fields():
    res = client.post(
        "/api/lore/entities",
        json={"title": "Bad Entity", "visibility": "made_up"},
    )
    assert res.status_code == 422


def test_get_and_patch_entity_404_for_unknown_id():
    assert client.get(f"/api/lore/entities/{NIL_UUID}").status_code == 404
    assert client.patch(f"/api/lore/entities/{NIL_UUID}", json={"title": "x"}).status_code == 404


def test_create_entity_rejects_duplicate_slug():
    first = client.post("/api/lore/entities", json={"slug": "dup-entity", "title": "Dup Entity"})
    assert first.status_code == 201
    second = client.post("/api/lore/entities", json={"slug": "dup-entity", "title": "Dup Entity 2"})
    assert second.status_code == 409


def test_entity_slug_defaults_from_title_when_omitted():
    res = client.post("/api/lore/entities", json={"title": "Kaguya Haiiro!"})
    assert res.status_code == 201
    assert res.json()["slug"] == "kaguya-haiiro"


# ---- lore/aliases --------------------------------------------------------


def test_get_alias_404_for_unknown_id():
    assert client.get(f"/api/lore/aliases/{NIL_UUID}").status_code == 404


def test_create_alias_404_when_entity_missing():
    res = client.post(f"/api/lore/entities/{NIL_UUID}/aliases", json={"alias": "Nope"})
    assert res.status_code == 404


def test_patch_alias_404_for_unknown_id():
    res = client.patch(f"/api/lore/aliases/{NIL_UUID}", json={"alias": "x"})
    assert res.status_code == 404


# ---- lore/sections --------------------------------------------------------


def test_get_and_patch_section_404_for_unknown_id():
    assert client.get(f"/api/lore/sections/{NIL_UUID}").status_code == 404
    assert client.patch(f"/api/lore/sections/{NIL_UUID}", json={"body": "x"}).status_code == 404


def test_create_section_404_when_entity_missing():
    source = client.post("/api/lore/sources", json={"source_path": "Lore/sec.md"}).json()
    res = client.post(
        f"/api/lore/entities/{NIL_UUID}/sections",
        json={"source_id": source["id"], "heading": "H", "body": "B"},
    )
    assert res.status_code == 404


def test_delete_section():
    source = client.post("/api/lore/sources", json={"source_path": "Lore/del.md"}).json()
    entity = client.post("/api/lore/entities", json={"title": "Del Entity"}).json()
    section = client.post(
        f"/api/lore/entities/{entity['id']}/sections",
        json={"source_id": source["id"], "heading": "H", "body": "B"},
    ).json()

    res = client.delete(f"/api/lore/sections/{section['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}
    assert client.get(f"/api/lore/sections/{section['id']}").status_code == 404


def test_delete_section_404_for_unknown_id():
    assert client.delete(f"/api/lore/sections/{NIL_UUID}").status_code == 404


# ---- relationships --------------------------------------------------------


def test_create_relationship_requires_target_id_or_unresolved_target():
    res = client.post(
        "/api/relationships",
        json={
            "source_type": "entity",
            "source_id": "some-entity",
            "target_type": "entity",
            "relationship_type": "mentions",
        },
    )
    assert res.status_code == 422


def test_create_relationship_accepts_unresolved_target():
    res = client.post(
        "/api/relationships",
        json={
            "source_type": "entity",
            "source_id": "some-entity",
            "target_type": "entity",
            "unresolved_target": "Unknown Figure",
            "relationship_type": "mentions",
        },
    )
    assert res.status_code == 201
    assert res.json()["unresolved_target"] == "Unknown Figure"


def test_relationship_review_requires_at_least_one_relationship():
    res = client.post(
        "/api/relationships/review",
        json={"relationships": []},
    )
    assert res.status_code == 422


def test_patch_relationship_404_for_unknown_id():
    res = client.patch(f"/api/relationships/{NIL_UUID}", json={"context": "x"})
    assert res.status_code == 404


def test_patch_relationship_requires_at_least_one_field():
    rel = client.post(
        "/api/relationships",
        json={
            "source_type": "entity",
            "source_id": "e1",
            "target_type": "entity",
            "target_id": "e2",
            "relationship_type": "mentions",
        },
    )
    assert rel.status_code == 201
    res = client.patch(f"/api/relationships/{rel.json()['id']}", json={})
    assert res.status_code == 422


# ---- lore/import/review --------------------------------------------------


def test_lore_import_review_rejects_unknown_target_type():
    res = client.post(
        "/api/lore/import/review",
        json={"target_type": "downtime_action"},
    )
    assert res.status_code == 422


def test_lore_import_review_rejects_invalid_surface():
    res = client.post(
        "/api/lore/import/review",
        json={"target_type": "entity", "source_surface": "made_up"},
    )
    assert res.status_code == 422


def test_lore_import_apply_delegates_to_generic_sync_apply():
    review = client.post(
        "/api/lore/import/review",
        json={"target_type": "entity", "target_id": "entity:some-entity"},
    )
    assert review.status_code == 201
    review_id = review.json()["id"]

    unconfirmed = client.post(f"/api/lore/import/{review_id}/apply", json={})
    assert unconfirmed.status_code == 422

    client.patch(
        f"/api/sync/reviews/{review_id}",
        json={"review_status": "accepted"},
    )
    applied = client.post(f"/api/lore/import/{review_id}/apply", json={"confirmation": True})
    assert applied.status_code == 409
    assert "vault_import" in applied.json()["detail"]


# ---- assets ---------------------------------------------------------------


def test_create_asset_rejects_invalid_enum_fields():
    bad_mirror = client.post(
        "/api/assets",
        json={"source_path": "Assets/x.png", "mirror_state": "made_up"},
    )
    assert bad_mirror.status_code == 422


def test_create_asset_rejects_invalid_status():
    res = client.post(
        "/api/assets",
        json={"source_path": "Assets/bad-status.png", "status": "made_up"},
    )
    assert res.status_code == 422


def test_patch_asset_rejects_invalid_status():
    created = client.post("/api/assets", json={"source_path": "Assets/patch-status.png"}).json()
    res = client.patch(f"/api/assets/{created['id']}", json={"status": "made_up"})
    assert res.status_code == 422


def test_create_asset_accepts_variant_and_rejected_status():
    variant = client.post(
        "/api/assets", json={"source_path": "Assets/variant.png", "status": "variant"}
    )
    assert variant.status_code == 201
    assert variant.json()["status"] == "variant"

    rejected = client.post(
        "/api/assets", json={"source_path": "Assets/rejected.png", "status": "rejected"}
    )
    assert rejected.status_code == 201
    assert rejected.json()["status"] == "rejected"


def test_create_asset_rejects_duplicate_source_path():
    first = client.post("/api/assets", json={"source_path": "Assets/dup.png"})
    assert first.status_code == 201
    second = client.post("/api/assets", json={"source_path": "Assets/dup.png"})
    assert second.status_code == 409


def test_get_and_patch_asset_404_for_unknown_id():
    assert client.get(f"/api/assets/{NIL_UUID}").status_code == 404
    assert client.patch(f"/api/assets/{NIL_UUID}", json={"title": "x"}).status_code == 404


def test_list_assets_filters_by_usage_and_linked_entity():
    entity = client.post("/api/lore/entities", json={"title": "Asset Owner"}).json()
    client.post(
        "/api/assets",
        json={
            "source_path": "Assets/owner-portrait.png",
            "usage": "portrait",
            "linked_entity_id": entity["id"],
        },
    )
    client.post("/api/assets", json={"source_path": "Assets/unrelated.png", "usage": "reference"})

    by_usage = client.get("/api/assets?usage=portrait")
    assert by_usage.status_code == 200
    assert [row["source_path"] for row in by_usage.json()] == ["Assets/owner-portrait.png"]

    by_entity = client.get(f"/api/assets?linked_entity_id={entity['id']}")
    assert by_entity.status_code == 200
    assert len(by_entity.json()) == 1


# ---- lore/import/scan --------------------------------------------------


def test_scan_lore_vault_dry_run_reports_summary_without_writing_reviews(tmp_path, monkeypatch):
    (tmp_path / "Lore" / "World_of_Rokugan" / "Locations").mkdir(parents=True)
    (tmp_path / "Lore" / "World_of_Rokugan" / "Locations" / "Kani.md").write_text(
        "# Kanigakure\n\n## Overview\nHome base.\n", encoding="utf-8"
    )
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    res = client.post("/api/lore/import/scan?dry_run=true")
    assert res.status_code == 200
    body = res.json()
    assert body["scanned"] == 1
    assert body["new"] == 1
    assert body["review_ids"] == []
    assert "sync_job_id" not in body

    listed = client.get("/api/sync/reviews?review_type=vault_import")
    assert listed.json() == []


def test_scan_lore_vault_creates_job_and_reviews(tmp_path, monkeypatch):
    (tmp_path / "Lore" / "World_of_Rokugan" / "Locations").mkdir(parents=True)
    (tmp_path / "Lore" / "World_of_Rokugan" / "Locations" / "Kani.md").write_text(
        "# Kanigakure\n\n## Overview\nHome base.\n", encoding="utf-8"
    )
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    res = client.post("/api/lore/import/scan")
    assert res.status_code == 200
    body = res.json()
    assert body["new"] == 1
    assert len(body["review_ids"]) == 1
    assert body["sync_job_id"]

    job = client.get(f"/api/sync/jobs/{body['sync_job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"
    assert job.json()["job_type"] == "vault_scan"

    review = client.get(f"/api/sync/reviews/{body['review_ids'][0]}")
    assert review.status_code == 200
    assert review.json()["review_type"] == "vault_import"


def test_scan_lore_vault_marks_job_failed_when_scan_raises(tmp_path, monkeypatch):
    (tmp_path / "Lore" / "World_of_Rokugan" / "Locations").mkdir(parents=True)
    (tmp_path / "Lore" / "World_of_Rokugan" / "Locations" / "Kani.md").write_text(
        "# Kanigakure\n\n## Overview\nHome base.\n", encoding="utf-8"
    )
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    def _boom(*args, **kwargs):
        raise RuntimeError("scan exploded")

    monkeypatch.setattr("gm_dashboard.lore_router.scan_vault", _boom)

    with pytest.raises(RuntimeError, match="scan exploded"):
        client.post("/api/lore/import/scan")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT status, error_code, error_message, finished_at FROM sync_jobs "
                "WHERE job_type = 'vault_scan' ORDER BY started_at DESC LIMIT 1"
            )
            row = dict(cur.fetchone())
    finally:
        conn.close()

    assert row["status"] == "failed"
    assert row["error_code"] == "scan_error"
    assert row["error_message"] == "scan exploded"
    assert row["finished_at"] is not None


# ---- assets/import/scan ----------------------------------------------------


def test_scan_assets_import_dry_run_reports_summary_without_writing_reviews(tmp_path, monkeypatch):
    from PIL import Image

    img_dir = tmp_path / "Lore" / "Assets" / "Images" / "NPCs"
    img_dir.mkdir(parents=True)
    Image.new("RGB", (4, 4)).save(img_dir / "scar.png")
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    res = client.post("/api/assets/import/scan?dry_run=true")
    assert res.status_code == 200
    body = res.json()
    assert body["scanned"] == 1
    assert body["new"] == 1
    assert body["review_ids"] == []
    assert "sync_job_id" not in body

    listed = client.get("/api/sync/reviews?review_type=asset_import")
    assert listed.json() == []


def test_scan_assets_import_creates_job_and_reviews(tmp_path, monkeypatch):
    from PIL import Image

    img_dir = tmp_path / "Lore" / "Assets" / "Images" / "NPCs"
    img_dir.mkdir(parents=True)
    Image.new("RGB", (4, 4)).save(img_dir / "scar.png")
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    res = client.post("/api/assets/import/scan")
    assert res.status_code == 200
    body = res.json()
    assert body["new"] == 1
    assert len(body["review_ids"]) == 1
    assert body["sync_job_id"]

    job = client.get(f"/api/sync/jobs/{body['sync_job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"
    assert job.json()["job_type"] == "asset_scan"

    review = client.get(f"/api/sync/reviews/{body['review_ids'][0]}")
    assert review.status_code == 200
    assert review.json()["review_type"] == "asset_import"

    decided = client.patch(f"/api/sync/reviews/{body['review_ids'][0]}", json={"review_status": "accepted"})
    assert decided.status_code == 200

    applied = client.post(
        f"/api/assets/import/{body['review_ids'][0]}/apply", json={"confirmation": True}
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] is True

    assets = client.get("/api/assets")
    assert [row["source_path"] for row in assets.json()] == ["Lore/Assets/Images/NPCs/scar.png"]
