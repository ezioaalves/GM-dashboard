from __future__ import annotations

import os
from pathlib import Path

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


@pytest.fixture(autouse=True)
def clean_assets():
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM lore_assets")
    conn.close()
    yield
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM lore_assets")
    conn.close()


def _insert_asset(source_path: str, source_hash: str, mirror_state: str = "mirrored") -> str:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_assets (source_path, source_hash, asset_type, mirror_state)
                VALUES (%s, %s, 'image', %s)
                RETURNING id
                """,
                (source_path, source_hash, mirror_state),
            )
            return str(cur.fetchone()["id"])
    finally:
        conn.close()


# A 1x1 transparent PNG.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000155075a7a0000000049454e44ae426082"
)


def test_get_asset_file_streams_bytes_for_existing_file(tmp_path, monkeypatch):
    rel = "Lore/Assets/Images/dot.png"
    (tmp_path / "Lore/Assets/Images").mkdir(parents=True)
    (tmp_path / rel).write_bytes(PNG_BYTES)
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))

    asset_id = _insert_asset(rel, "abc123")
    res = client.get(f"/api/assets/{asset_id}/file")

    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.headers["etag"] == "abc123"
    assert res.content == PNG_BYTES


def test_get_asset_file_404s_when_file_missing_on_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("KAIHOU_VAULT_ROOT", str(tmp_path))
    asset_id = _insert_asset("Lore/Assets/Images/missing.png", "abc123", mirror_state="missing_source")

    res = client.get(f"/api/assets/{asset_id}/file")

    assert res.status_code == 404
    assert "missing_source" in res.json()["detail"]


def test_get_asset_file_404s_for_unknown_asset_id():
    res = client.get("/api/assets/00000000-0000-0000-0000-000000000000/file")
    assert res.status_code == 404
