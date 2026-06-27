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


def test_ticket_stage_parsing(tmp_path):
    seed_vault(tmp_path)
    tickets = services.ticket_files(tmp_path)
    assert tickets[0]["stage"] == "now"
    assert tickets[0]["next_action"] == "Build first screen"


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
