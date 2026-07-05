from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

from gm_dashboard.asset_scan import (
    compute_asset_hash,
    is_rejected_path,
    read_image_dimensions,
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
)


def _connect():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _clean() -> None:
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM lore_assets")
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
    conn.close()


@pytest.fixture(autouse=True)
def clean_asset_tables():
    _clean()
    yield
    _clean()


def test_compute_asset_hash_is_stable_sha256():
    assert compute_asset_hash(b"hello") == compute_asset_hash(b"hello")
    assert compute_asset_hash(b"hello") != compute_asset_hash(b"hello ")
    assert len(compute_asset_hash(b"hello")) == 64


def test_is_rejected_path_matches_rejected_folder_case_insensitively():
    assert is_rejected_path("Lore/Assets/Images/Rejected/old_v1.png") is True
    assert is_rejected_path("Lore/Assets/Images/REJECTED/old_v1.png") is True
    assert is_rejected_path("Lore/Assets/Images/NPCs/portrait.png") is False


def test_read_image_dimensions_reads_a_real_png(tmp_path):
    from PIL import Image

    png_path = tmp_path / "test.png"
    Image.new("RGB", (12, 34)).save(png_path)

    width, height = read_image_dimensions(png_path)
    assert (width, height) == (12, 34)


def test_read_image_dimensions_returns_none_for_undecodable_file(tmp_path):
    bogus = tmp_path / "bogus.png"
    bogus.write_bytes(b"not a real png")

    width, height = read_image_dimensions(bogus)
    assert (width, height) == (None, None)


from gm_dashboard.asset_scan import scan_assets


def _write_png(tmp_path: Path, rel_path: str, size: tuple[int, int] = (4, 4)) -> Path:
    from PIL import Image

    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size).save(full)
    return full


def test_scan_assets_creates_one_pending_review_per_new_file(tmp_path):
    _write_png(tmp_path, "Lore/Assets/Images/NPCs/scar.png", size=(10, 20))

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_assets(tmp_path, cur)
    finally:
        conn.close()

    assert summary["scanned"] == 1
    assert summary["new"] == 1
    assert summary["unchanged"] == 0
    assert summary["changed_on_disk"] == 0
    assert summary["missing"] == 0
    assert summary["conflicts"] == 0
    assert len(summary["review_ids"]) == 1

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT review_type, target_type, review_status, proposed_changes FROM sync_reviews")
            review = dict(cur.fetchone())
    finally:
        conn.close()

    assert review["review_type"] == "asset_import"
    assert review["target_type"] == "asset"
    assert review["review_status"] == "pending"
    proposed = review["proposed_changes"]
    assert proposed["source_path"] == "Lore/Assets/Images/NPCs/scar.png"
    assert proposed["asset_type"] == "image"
    assert proposed["status"] == "current"
    assert proposed["title"] == "scar"
    assert proposed["width"] == 10
    assert proposed["height"] == 20


def test_scan_assets_marks_rejected_folder_files_as_rejected_status(tmp_path):
    _write_png(tmp_path, "Lore/Assets/Images/Rejected/old_variant.png")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            scan_assets(tmp_path, cur)
            cur.execute("SELECT proposed_changes FROM sync_reviews")
            proposed = cur.fetchone()["proposed_changes"]
    finally:
        conn.close()

    assert proposed["status"] == "rejected"


def test_scan_assets_dry_run_creates_no_reviews(tmp_path):
    _write_png(tmp_path, "Lore/Assets/Images/NPCs/scar.png")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_assets(tmp_path, cur, dry_run=True)
            cur.execute("SELECT count(*) AS n FROM sync_reviews")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert summary["new"] == 1
    assert summary["review_ids"] == []
    assert count == 0


def test_scan_assets_is_idempotent_for_unchanged_and_pending_sources(tmp_path):
    _write_png(tmp_path, "Lore/Assets/Images/NPCs/scar.png")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            first = scan_assets(tmp_path, cur)
            second = scan_assets(tmp_path, cur)
            cur.execute("SELECT count(*) AS n FROM sync_reviews")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert first["new"] == 1
    assert len(first["review_ids"]) == 1
    assert second["new"] == 1
    assert second["review_ids"] == []
    assert count == 1


def test_scan_assets_flags_duplicate_content_as_conflict(tmp_path):
    _write_png(tmp_path, "Lore/Assets/Images/NPCs/original.png", size=(5, 5))

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_assets (source_path, source_hash, asset_type)
                VALUES ('Lore/Assets/Images/NPCs/already-registered.png',
                        %s, 'image')
                """,
                (compute_asset_hash((tmp_path / "Lore/Assets/Images/NPCs/original.png").read_bytes()),),
            )
            summary = scan_assets(tmp_path, cur)
            cur.execute(
                "SELECT proposed_changes, conflict_flags FROM sync_reviews WHERE review_type = 'asset_import'"
            )
            review = dict(cur.fetchone())
    finally:
        conn.close()

    assert summary["conflicts"] == 1
    assert review["conflict_flags"] == ["duplicate_content"]
    assert review["proposed_changes"]["duplicate_of"] == "Lore/Assets/Images/NPCs/already-registered.png"


def test_scan_assets_ignores_files_outside_extension_set(tmp_path):
    other = tmp_path / "Lore" / "Assets" / "notes.txt"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("not an image")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_assets(tmp_path, cur)
    finally:
        conn.close()

    assert summary["scanned"] == 0
    assert summary["review_ids"] == []


def test_scan_assets_returns_zeroed_summary_when_assets_dir_missing(tmp_path):
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_assets(tmp_path, cur)
    finally:
        conn.close()

    assert summary == {
        "scanned": 0, "new": 0, "changed_on_disk": 0, "missing": 0,
        "conflicts": 0, "unchanged": 0, "errors": 0, "review_ids": [],
    }
