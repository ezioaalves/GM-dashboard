from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

from gm_dashboard.lore_scan import (
    classify_entity_type,
    compute_source_hash,
    extract_wikilinks,
    is_scannable,
    parse_sections,
    parse_frontmatter,
    parse_source_file,
    parse_title,
    slugify,
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


def test_compute_source_hash_is_stable_sha256():
    assert compute_source_hash("hello") == compute_source_hash("hello")
    assert compute_source_hash("hello") != compute_source_hash("hello ")
    assert len(compute_source_hash("hello")) == 64


def test_slugify_lowercases_and_dashes():
    assert slugify("The Shadowlands (Jigoku)") == "the-shadowlands-jigoku"
    assert slugify("   ") == "entity"


def test_parse_title_uses_first_h1_or_falls_back_to_filename():
    assert parse_title("# The Shadowlands\n\nBody.", Path("x.md")) == "The Shadowlands"
    assert parse_title("No heading here.", Path("Foo_Bar.md")) == "Foo_Bar"


def test_canonical_frontmatter_controls_dashboard_identity_and_kind():
    text = (
        "---\n"
        "schema: kaihou-record/v1\n"
        "kaihou_id: 4ac2e340-3bf5-4d8c-8244-2bc84e47f9e3\n"
        "kind: npc\n"
        "title: Garou Do\n"
        "slug: garou-do\n"
        "---\n\n"
        "# Garou Do\n"
    )
    assert parse_frontmatter(text)["kaihou_id"] == "4ac2e340-3bf5-4d8c-8244-2bc84e47f9e3"
    parsed = parse_source_file("10-canon/characters/npcs/Garou_Do.md", text)
    assert parsed["kaihou_id"] == "4ac2e340-3bf5-4d8c-8244-2bc84e47f9e3"
    assert parsed["entity_type"] == "npc"
    assert parsed["slug"] == "garou-do"


def test_classify_entity_type_by_folder_prefix():
    assert classify_entity_type("Lore/NPCs/Scar/Scar_Sheet.md") == "npc"
    assert classify_entity_type("Lore/Player_Characters/Aburame Suigin/Sheet.md") == "pc"
    assert classify_entity_type("Lore/World_of_Rokugan/Locations/The_Shadowlands/01.md") == "location"
    assert classify_entity_type("Lore/World_of_Rokugan/Kanigakure/Overview.md") == "location"
    assert classify_entity_type("Lore/World_of_Rokugan/Great_Nations/Fire.md") == "faction"
    assert classify_entity_type("Lore/World_of_Rokugan/History_and_Lore/Origins.md") == "article"
    assert classify_entity_type("Lore/Lore_Registry.md") == "article"


def test_parse_sections_splits_by_heading_and_tracks_heading_path():
    text = (
        "# Title\n"
        "\n"
        "Intro paragraph, not a section.\n"
        "\n"
        "## Overview\n"
        "First body.\n"
        "\n"
        "### Nested\n"
        "Nested body.\n"
        "\n"
        "## Second\n"
        "Second body.\n"
    )
    sections = parse_sections(text)
    assert [s["heading"] for s in sections] == ["Overview", "Nested", "Second"]
    assert sections[0]["heading_path"] == ["Overview"]
    assert sections[1]["heading_path"] == ["Overview", "Nested"]
    assert sections[2]["heading_path"] == ["Second"]
    assert sections[0]["body"] == "First body."
    assert sections[1]["body"] == "Nested body."
    assert sections[2]["body"] == "Second body."
    assert sections[0]["section_order"] == 0
    assert sections[2]["section_order"] == 2


def test_parse_sections_handles_no_headings():
    assert parse_sections("Just a paragraph, no headings at all.") == []


def test_extract_wikilinks_finds_plain_aliased_and_embedded_links():
    text = (
        "See [[Kanigakure]] and [[Scar|the deserter]] "
        "and [[folder/Fu Leng#Goal]].\n"
        "![[village_map.png]]\n"
    )
    links = extract_wikilinks(text)
    assert {"target": "Kanigakure", "is_embed": False} in links
    assert {"target": "Scar", "is_embed": False} in links
    assert {"target": "folder/Fu Leng", "is_embed": False} in links
    assert {"target": "village_map.png", "is_embed": True} in links


def test_is_scannable_excludes_drafts_and_templates():
    vault_root = Path("/vault")
    assert is_scannable(Path("/vault/Lore/NPCs/Scar/Sheet.md"), vault_root) is True
    assert is_scannable(Path("/vault/Lore/NPCs/_drafts/Draft.md"), vault_root) is False
    assert is_scannable(Path("/vault/Lore/NPCs/_NPC_Template.md"), vault_root) is False


from gm_dashboard.lore_scan import build_relationships, diff_sections, parse_source_file


def test_parse_source_file_combines_title_slug_type_sections_and_links():
    text = "# Kanigakure\n\n## Overview\nHome of the Wakizashi. [[Scar]]\n"
    parsed = parse_source_file("Lore/World_of_Rokugan/Kanigakure/Overview.md", text)
    assert parsed["title"] == "Kanigakure"
    assert parsed["slug"] == "kanigakure"
    assert parsed["entity_type"] == "location"
    assert [s["heading"] for s in parsed["sections"]] == ["Overview"]
    assert parsed["links"] == [{"target": "Scar", "is_embed": False}]


def test_build_relationships_resolves_known_targets_and_flags_unknown():
    def resolve(target):
        if target == "Scar":
            return {"graph_endpoint_id": "entity:11111111-1111-1111-1111-111111111111"}
        return None

    links = [
        {"target": "Scar", "is_embed": False},
        {"target": "Nobody", "is_embed": False},
        {"target": "village_map.png", "is_embed": True},
    ]
    relationships = build_relationships(links, resolve)

    assert relationships[0] == {
        "source_type": "entity",
        "target_type": "entity",
        "relationship_type": "mentions",
        "provenance": "wikilink",
        "target_id": "entity:11111111-1111-1111-1111-111111111111",
    }
    assert relationships[1] == {
        "source_type": "entity",
        "target_type": "entity",
        "relationship_type": "mentions",
        "provenance": "wikilink",
        "unresolved_target": "Nobody",
    }
    assert relationships[2] == {
        "source_type": "entity",
        "target_type": "asset",
        "relationship_type": "embeds",
        "provenance": "asset_embed",
        "unresolved_target": "village_map.png",
    }


def test_diff_sections_reports_added_removed_and_modified():
    existing = [
        {"heading": "Overview", "body": "old body", "heading_path": ["Overview"]},
        {"heading": "Gone", "body": "bye", "heading_path": ["Gone"]},
    ]
    parsed = [
        {"heading": "Overview", "body": "new body", "heading_path": ["Overview"], "section_order": 0},
        {"heading": "New", "body": "hi", "heading_path": ["New"], "section_order": 1},
    ]
    result = diff_sections(existing, parsed)
    assert result["removed"] == ["Gone"]
    assert [s["heading"] for s in result["added"]] == ["New"]
    assert [s["heading"] for s in result["modified"]] == ["Overview"]


def test_diff_sections_reports_nothing_when_unchanged():
    existing = [{"heading": "Overview", "body": "same", "heading_path": ["Overview"]}]
    parsed = [{"heading": "Overview", "body": "same", "heading_path": ["Overview"], "section_order": 0}]
    result = diff_sections(existing, parsed)
    assert result == {"added": [], "removed": [], "modified": []}


from gm_dashboard.lore_scan import scan_vault


def _write(tmp_path, rel_path, text):
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text, encoding="utf-8")
    return full


def test_scan_vault_creates_one_pending_review_per_new_file(tmp_path):
    _write(tmp_path, "Lore/World_of_Rokugan/Locations/Kani.md", "# Kanigakure\n\n## Overview\nHome base.\n")
    _write(tmp_path, "Lore/World_of_Rokugan/Locations/Scar.md", "# Scar\n\n## Overview\nA deserter.\n")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_vault(tmp_path, cur)
    finally:
        conn.close()

    assert summary["scanned"] == 2
    assert summary["new"] == 2
    assert summary["changed"] == 0
    assert summary["unchanged"] == 0
    assert len(summary["review_ids"]) == 2

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT review_type, target_type, review_status, proposed_changes FROM sync_reviews ORDER BY created_at")
            rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    assert len(rows) == 2
    assert all(row["review_type"] == "vault_import" for row in rows)
    assert all(row["target_type"] == "entity" for row in rows)
    assert all(row["review_status"] == "pending" for row in rows)
    slugs = {row["proposed_changes"]["entity"]["slug"] for row in rows}
    assert slugs == {"kanigakure", "scar"}


def test_scan_vault_skips_drafts_and_templates(tmp_path):
    _write(tmp_path, "Lore/NPCs/_NPC_Template.md", "# Template\n")
    _write(tmp_path, "Lore/NPCs/_drafts/Draft.md", "# Draft\n")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_vault(tmp_path, cur)
    finally:
        conn.close()

    assert summary["scanned"] == 0
    assert summary["review_ids"] == []


def test_scan_vault_skips_unreadable_file_and_counts_it_as_error(tmp_path):
    _write(tmp_path, "Lore/World_of_Rokugan/Locations/Kani.md", "# Kanigakure\n\n## Overview\nHome base.\n")
    bad = tmp_path / "Lore" / "World_of_Rokugan" / "Locations" / "Bad.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"\xff\xfe# Bad\n")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_vault(tmp_path, cur)
    finally:
        conn.close()

    assert summary["new"] == 1
    assert summary["errors"] == 1
    assert len(summary["review_ids"]) == 1


def test_scan_vault_dry_run_creates_no_reviews(tmp_path):
    _write(tmp_path, "Lore/World_of_Rokugan/Locations/Kani.md", "# Kanigakure\n\n## Overview\nHome base.\n")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_vault(tmp_path, cur, dry_run=True)
            cur.execute("SELECT count(*) AS n FROM sync_reviews")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert summary["new"] == 1
    assert summary["review_ids"] == []
    assert count == 0


def test_scan_vault_is_idempotent_for_unchanged_and_pending_sources(tmp_path):
    _write(tmp_path, "Lore/World_of_Rokugan/Locations/Kani.md", "# Kanigakure\n\n## Overview\nHome base.\n")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            first = scan_vault(tmp_path, cur)
            second = scan_vault(tmp_path, cur)
            cur.execute("SELECT count(*) AS n FROM sync_reviews")
            count = cur.fetchone()["n"]
    finally:
        conn.close()

    assert first["new"] == 1
    assert len(first["review_ids"]) == 1
    assert second["new"] == 1
    assert second["review_ids"] == []
    assert count == 1


def test_scan_vault_reports_changed_and_diffs_sections_against_committed_entity(tmp_path):
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_entities (slug, title, entity_type, source_path, source_hash)
                VALUES ('kanigakure', 'Kanigakure', 'location',
                        'Lore/World_of_Rokugan/Locations/Kani.md', 'old-hash')
                RETURNING id
                """
            )
            entity_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO lore_sources (source_surface, source_path, source_hash)
                VALUES ('vault', 'Lore/World_of_Rokugan/Locations/Kani.md', 'old-hash')
                RETURNING id
                """
            )
            source_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO lore_sections (source_id, entity_id, heading, body, section_order, heading_path)
                VALUES (%s, %s, 'Overview', 'Old home base.', 0, %s)
                """,
                (source_id, entity_id, ["Overview"]),
            )
    finally:
        conn.close()

    _write(tmp_path, "Lore/World_of_Rokugan/Locations/Kani.md", "# Kanigakure\n\n## Overview\nNew home base.\n")

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_vault(tmp_path, cur)
            cur.execute("SELECT target_id, proposed_changes FROM sync_reviews")
            review = dict(cur.fetchone())
    finally:
        conn.close()

    assert summary["changed"] == 1
    assert summary["new"] == 0
    assert review["target_id"] == f"entity:{entity_id}"
    assert review["proposed_changes"]["diff_kind"] == "changed"
    modified_headings = [s["heading"] for s in review["proposed_changes"]["section_diff"]["modified"]]
    assert modified_headings == ["Overview"]


def test_scan_vault_resolves_wikilink_to_already_committed_entity(tmp_path):
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_entities (slug, title, entity_type, source_path, source_hash)
                VALUES ('scar', 'Scar', 'npc', 'Lore/NPCs/Scar.md', 'hash-scar')
                RETURNING id, graph_endpoint_id
                """
            )
            scar = dict(cur.fetchone())
    finally:
        conn.close()

    _write(
        tmp_path,
        "Lore/World_of_Rokugan/Locations/Kani.md",
        "# Kanigakure\n\n## Overview\nHome of [[Scar]].\n",
    )

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            scan_vault(tmp_path, cur)
            cur.execute("SELECT proposed_changes FROM sync_reviews")
            review = cur.fetchone()["proposed_changes"]
    finally:
        conn.close()

    relationships = review["relationships"]
    assert len(relationships) == 1
    assert relationships[0]["target_id"] == scar["graph_endpoint_id"]
