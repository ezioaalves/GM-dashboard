from __future__ import annotations

from pathlib import Path

from gm_dashboard import services


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def seed_vault(root: Path) -> None:
    write(root / "Campaign Management/session-logs/16-old.md", """---
schema_version: 1
session: 16
date: 2026-06-01
title: Old
---

# Session 16 - Old
""")
    write(root / "Campaign Management/session-logs/17-red-in-the-forest.md", """---
schema_version: 1
session: 17
date: 2026-06-15
title: Red in the Forest
npcs_present: [Kaguya_Haiiro]
locations: [Shadowlands]
---

# Session 17 - Red in the Forest

## What happened

The party fled the Tetsu no Oni. Haiiro was missing.

## Notable moments

- Haiiro vanished.
- The Tetsu no Oni appeared.
""")
    write(root / "Campaign Management/01 - Live/Next_Session.md", "# stale prep\n")
    write(root / "Campaign Management/operational/tickets/kaihou-gm-webapp-session-cockpit.md", """---
schema_version: 2
id: kaihou-gm-webapp-session-cockpit
title: Session cockpit
status: in_progress
area: docs
priority: high
stage: now
next_action: Build first screen
---

# Session cockpit

Make the first screen useful.
""")


def test_latest_session_selects_highest_number(tmp_path):
    seed_vault(tmp_path)
    latest = services.latest_session_log(tmp_path)
    assert latest["session"] == 17
    assert latest["title"] == "Red in the Forest"
    assert "Tetsu no Oni" in latest["summary"]


def test_cockpit_seeds_leaveoff_from_session_17(tmp_path):
    seed_vault(tmp_path)
    cockpit = services.cockpit_session(tmp_path)
    assert cockpit["latest_session"]["session"] == 17
    assert cockpit["leave_off"]["detail"] == (
        "Party is fleeing the Tetsu no Oni in hostile forest; Haiiro is missing."
    )
    assert cockpit["columns"]["scene_deck"][0]["id"] == "survive-the-forest"



def test_draft_session_note_and_save_path(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_session_note("Forest escape and Haiiro search.", tmp_path)
    assert draft["id"].startswith("session-18-")
    assert "Forest escape" in draft["markdown"]
    assert draft["default_target_path"] == "Campaign Management/session-logs/18-forest-escape-and-haiiro-search.md"

    target = "Campaign Management/session-logs/18-forest-escape.md"
    preview = services.preview_draft_save(draft["id"], target, tmp_path)
    assert preview["saved"] is False
    assert preview["path"] == target
    assert preview["target_exists"] is False
    assert "Forest escape" in preview["markdown"]

    edited = draft["markdown"].replace("Forest escape", "Edited forest escape")
    edited_preview = services.preview_draft_save(draft["id"], target, tmp_path, markdown=edited)
    assert "Edited forest escape" in edited_preview["markdown"]

    try:
        services.save_draft(draft["id"], target, tmp_path)
    except services.VaultError as exc:
        assert "confirm=true" in str(exc)
    else:
        raise AssertionError("expected VaultError")

    saved = services.save_draft(draft["id"], target, tmp_path, markdown=edited, confirm=True)
    assert saved["saved"] is True
    assert (tmp_path / saved["path"]).exists()
    assert "Edited forest escape" in (tmp_path / saved["path"]).read_text()
    assert "Edited forest escape" in (tmp_path / draft["path"]).read_text()


def test_scene_draft_has_canonical_save_flow(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_scene({"title": "Forest Choice", "purpose": "Pick route"}, tmp_path)
    assert draft["default_target_path"] == "Campaign Management/01 - Live/Current Situation/forest-choice.md"

    preview = services.preview_draft_save(draft["id"], draft["default_target_path"], tmp_path)
    assert preview["saved"] is False
    assert "Pick route" in preview["markdown"]

    saved = services.save_draft(draft["id"], draft["default_target_path"], tmp_path, confirm=True)
    assert saved["saved"] is True
    assert (tmp_path / saved["path"]).exists()


def test_canonical_save_rejects_drafts_target(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_scene({"title": "Bad Target"}, tmp_path)
    try:
        services.preview_draft_save(
            draft["id"],
            "Campaign Management/01 - Live/Current Situation/_drafts/bad-target.md",
            tmp_path,
        )
    except services.VaultError as exc:
        assert "cannot be inside _drafts" in str(exc)
    else:
        raise AssertionError("expected VaultError")


def test_search_vault_finds_markdown(tmp_path):
    seed_vault(tmp_path)
    results = services.search_vault("Haiiro", tmp_path)
    assert results
    assert any("17-red-in-the-forest.md" in row["path"] for row in results)


def test_open_and_save_vault_markdown(tmp_path):
    seed_vault(tmp_path)
    rel = "Campaign Management/session-logs/17-red-in-the-forest.md"
    opened = services.vault_markdown_file(rel, tmp_path)
    assert opened["path"] == rel
    assert "Haiiro was missing" in opened["markdown"]

    updated = opened["markdown"] + "\n<!-- cockpit edit test -->\n"
    saved = services.save_vault_markdown_file(rel, updated, tmp_path)
    assert saved["path"] == rel
    assert "cockpit edit test" in (tmp_path / rel).read_text()


def test_open_markdown_rejects_path_escape(tmp_path):
    seed_vault(tmp_path)
    try:
      services.vault_markdown_file("../outside.md", tmp_path)
    except services.VaultError as exc:
      assert "escapes vault" in str(exc)
    else:
      raise AssertionError("expected VaultError")


def test_session_note_context_no_threads_dir(tmp_path):
    seed_vault(tmp_path)
    ctx = services.session_note_context(tmp_path)
    assert ctx["latest_session"]["session"] == 17
    assert ctx["npc_list"] == ["Kaguya_Haiiro"]
    assert ctx["live_prep_excerpt"].startswith("# stale prep")
    assert ctx["active_threads"] == []


def test_session_note_context_surfaces_active_threads(tmp_path):
    seed_vault(tmp_path)
    write(
        tmp_path / "Campaign Management/authorial/threads/onimusha.md",
        """---
schema_version: 1
id: onimusha-team-identity
title: The Onimusha
status: active
next_move: What will they do next?
---

# The Onimusha
""",
    )
    ctx = services.session_note_context(tmp_path)
    assert len(ctx["active_threads"]) == 1
    assert ctx["active_threads"][0]["id"] == "onimusha-team-identity"
    assert ctx["active_threads"][0]["next_move"] == "What will they do next?"


def test_session_note_context_inactive_threads_excluded(tmp_path):
    seed_vault(tmp_path)
    write(
        tmp_path / "Campaign Management/authorial/threads/closed.md",
        """---
id: closed-thread
title: Old Thread
status: resolved
next_move: ""
---
""",
    )
    ctx = services.session_note_context(tmp_path)
    assert ctx["active_threads"] == []


def test_session_note_context_missing_live_prep(tmp_path):
    write(
        tmp_path / "Campaign Management/session-logs/17-test.md",
        """---
schema_version: 1
session: 17
date: 2026-06-15
title: Test
---
""",
    )
    ctx = services.session_note_context(tmp_path)
    assert ctx["live_prep_excerpt"] == ""


def test_draft_session_note_structured_sections(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_session_note(
        "",
        tmp_path,
        scenes=["Party escapes the forest", "Dan spots the patrol beacon"],
        npcs_present=["Dan", "Ikazuchi"],
        clues_discovered=["The scroll was forged"],
        threads_touched=["onimusha-team-identity"],
        unresolved_questions=["Where is Haiiro?"],
        next_session_hook="Party emerges at dawn",
    )
    md = draft["markdown"]
    assert "1. Party escapes the forest" in md
    assert "2. Dan spots the patrol beacon" in md
    assert "- Dan" in md
    assert "- The scroll was forged" in md
    assert "- onimusha-team-identity" in md
    assert "- Where is Haiiro?" in md
    assert "Party emerges at dawn" in md


def test_draft_session_note_todo_markers_when_empty(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_session_note("", tmp_path)
    md = draft["markdown"]
    assert "<!-- TODO: add scene summaries" in md
    assert "<!-- TODO: list NPCs present" in md
    assert "<!-- TODO: list clues discovered" in md
    assert "<!-- TODO: list threads/clocks touched" in md
    assert "<!-- TODO: list unresolved questions" in md
    assert "<!-- TODO: set next-session hook" in md
    assert "<!-- TODO: add GM continuity notes" in md


def test_draft_session_note_title_prefers_hook(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_session_note(
        "some memory",
        tmp_path,
        next_session_hook="Dawn in the forest",
    )
    assert "dawn-in-the-forest" in draft["default_target_path"]


def test_draft_session_note_title_falls_back_to_first_scene(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_session_note(
        "",
        tmp_path,
        scenes=["Forest escape"],
    )
    assert "forest-escape" in draft["default_target_path"]


def test_draft_session_note_title_with_quotes_produces_valid_yaml(tmp_path):
    seed_vault(tmp_path)
    draft = services.draft_session_note(
        "",
        tmp_path,
        next_session_hook='"Dawn" in the forest',
    )
    fm, _ = services.split_frontmatter(draft["markdown"], Path("test"))
    assert "Dawn" in fm["title"]
