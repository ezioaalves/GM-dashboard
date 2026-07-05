from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

from gm_dashboard.sheet_scan import sync_npc_sheets, sync_pc_sheets

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
        cur.execute("DELETE FROM npcs")
        cur.execute("DELETE FROM pcs")
        cur.execute("DELETE FROM lore_entities")
    conn.close()


@pytest.fixture(autouse=True)
def clean_tables():
    _clean()
    yield
    _clean()


def _insert_entity(entity_type: str, slug: str, title: str, source_path: str,
                    review_status: str = "accepted") -> str:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_entities (slug, title, entity_type, source_path, review_status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (slug, title, entity_type, source_path, review_status),
            )
            return str(cur.fetchone()["id"])
    finally:
        conn.close()


NPC_SHEET = """---
foundry_actor_id_test: Actor.test123
foundry_actor_id_prod:
name: Dattoumaru Hayai
img: Lore/Assets/NPCs/Hayai.png
abilities: {str: 12, dex: 18, con: 14, int: 12, wis: 12, cha: 10}
naruto_stats: {actionPoints: 0, reputation: 1, wealth: 1, eps: 0}
---
# Dattoumaru Hayai
"""

PC_SHEET = """---
foundry_actor_id_prod: Actor.pcprod1
name: Suigin
abilities: {str: 14, dex: 16, con: 16, int: 14, wis: 12, cha: 8}
classes:
- {name: Fast Paragon, level: 3, subType: base}
---
# Suigin
"""

BROKEN_SHEET = """---
abilities: {str: 12
foo: bar
---
body
"""


def _write_sheet(tmp_path: Path, rel_path: str, text: str) -> None:
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text)


def test_sync_npc_sheets_creates_row_from_frontmatter(tmp_path):
    _write_sheet(tmp_path, "Lore/NPCs/Hayai_Sheet.md", NPC_SHEET)
    entity_id = _insert_entity("npc", "hayai", "Dattoumaru Hayai", "Lore/NPCs/Hayai_Sheet.md")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = sync_npc_sheets(tmp_path, cur)
            cur.execute("SELECT * FROM npcs WHERE slug = 'hayai'")
            npc = dict(cur.fetchone())
    finally:
        conn.close()

    assert summary == {"scanned": 1, "synced": 1, "errors": []}
    assert npc["name"] == "Dattoumaru Hayai"
    assert npc["img_path"] == "Lore/Assets/NPCs/Hayai.png"
    assert str(npc["lore_entity_id"]) == entity_id
    assert npc["foundry_actor_id_test"] == "Actor.test123"
    assert npc["foundry_actor_id_prod"] is None
    assert npc["stats"]["abilities"]["dex"] == 18
    assert npc["stats"]["naruto_stats"]["reputation"] == 1


def test_sync_npc_sheets_ignores_pending_entities(tmp_path):
    _write_sheet(tmp_path, "Lore/NPCs/Hayai_Sheet.md", NPC_SHEET)
    _insert_entity("npc", "hayai", "Dattoumaru Hayai", "Lore/NPCs/Hayai_Sheet.md",
                    review_status="pending")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = sync_npc_sheets(tmp_path, cur)
    finally:
        conn.close()

    assert summary == {"scanned": 0, "synced": 0, "errors": []}


def test_sync_npc_sheets_does_not_erase_existing_foundry_actor_id_on_blank_frontmatter(tmp_path):
    _write_sheet(tmp_path, "Lore/NPCs/Hayai_Sheet.md", NPC_SHEET)
    _insert_entity("npc", "hayai", "Dattoumaru Hayai", "Lore/NPCs/Hayai_Sheet.md")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sync_npc_sheets(tmp_path, cur)
            # Simulate a push having set the prod id directly (frontmatter's prod field stays blank).
            cur.execute("UPDATE npcs SET foundry_actor_id_prod = 'Actor.prod999' WHERE slug = 'hayai'")
            sync_npc_sheets(tmp_path, cur)
            cur.execute("SELECT foundry_actor_id_prod FROM npcs WHERE slug = 'hayai'")
            prod_id = cur.fetchone()["foundry_actor_id_prod"]
    finally:
        conn.close()

    assert prod_id == "Actor.prod999"


def test_sync_npc_sheets_reports_unparseable_yaml_as_error_not_raised(tmp_path):
    _write_sheet(tmp_path, "Lore/NPCs/Broken_Sheet.md", BROKEN_SHEET)
    _insert_entity("npc", "broken", "Broken", "Lore/NPCs/Broken_Sheet.md")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = sync_npc_sheets(tmp_path, cur)
            cur.execute("SELECT count(*) AS n FROM npcs")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert summary["scanned"] == 1
    assert summary["synced"] == 0
    assert len(summary["errors"]) == 1
    assert summary["errors"][0]["vault_path"] == "Lore/NPCs/Broken_Sheet.md"
    assert count == 0


def test_sync_pc_sheets_creates_row_for_pc_entity_type(tmp_path):
    _write_sheet(tmp_path, "Lore/Player_Characters/Suigin/Suigin_Sheet.md", PC_SHEET)
    _insert_entity("pc", "suigin", "Suigin", "Lore/Player_Characters/Suigin/Suigin_Sheet.md")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = sync_pc_sheets(tmp_path, cur)
            cur.execute("SELECT * FROM pcs WHERE slug = 'suigin'")
            pc = dict(cur.fetchone())
    finally:
        conn.close()

    assert summary == {"scanned": 1, "synced": 1, "errors": []}
    assert pc["name"] == "Suigin"
    assert pc["foundry_actor_id_prod"] == "Actor.pcprod1"
    assert pc["stats"]["classes"][0]["name"] == "Fast Paragon"


def test_sync_npc_sheets_is_idempotent(tmp_path):
    _write_sheet(tmp_path, "Lore/NPCs/Hayai_Sheet.md", NPC_SHEET)
    _insert_entity("npc", "hayai", "Dattoumaru Hayai", "Lore/NPCs/Hayai_Sheet.md")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            first = sync_npc_sheets(tmp_path, cur)
            second = sync_npc_sheets(tmp_path, cur)
            cur.execute("SELECT count(*) AS n FROM npcs")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert first["synced"] == 1
    assert second["synced"] == 1
    assert count == 1
