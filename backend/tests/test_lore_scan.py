from __future__ import annotations

from pathlib import Path

from gm_dashboard.lore_scan import (
    classify_entity_type,
    compute_source_hash,
    extract_wikilinks,
    is_scannable,
    parse_sections,
    parse_title,
    slugify,
)


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
