from __future__ import annotations

import pytest

from gm_dashboard.foundry_journals import create_journal, render_scene_journal_html, update_journal
from gm_dashboard.relay_client import RelayError


class FakeJournalRelay:
    def __init__(self):
        self.journals: dict[str, str] = {}
        self.fail = False

    def execute_js(self, script: str) -> dict:
        if self.fail:
            return {"ok": False, "error": "relay down"}
        if "JournalEntry.implementation.create" in script:
            uuid = "JournalEntry.new1"
            self.journals[uuid] = "<created>"
            return {"ok": True, "uuid": uuid}
        # update path
        for uuid in self.journals:
            if uuid in script:
                self.journals[uuid] = "<updated>"
                return {"ok": True, "uuid": uuid}
        return {"ok": False, "error": "journal not found"}


def test_render_scene_journal_html_includes_core_fields():
    scene = {
        "id": 1, "title": "Ambush at the Gate", "description": "A trap springs.",
        "purpose": "Raise stakes", "opening_image": "Smoke rising", "sensory_words": "Acrid, loud",
        "cast": ["Hayai"], "location": ["Kanigakure Gate"],
    }
    html = render_scene_journal_html(scene, [])
    assert "Ambush at the Gate" in html
    assert "A trap springs." in html
    assert "Raise stakes" in html
    assert "Hayai" in html
    assert "Kanigakure Gate" in html


def test_render_scene_journal_html_includes_mirrored_images():
    scene = {"id": 1, "title": "Scene"}
    mirrored = [{"foundry_path": "worlds/kaihou/assets/gate.png", "title": "Gate"}]
    html = render_scene_journal_html(scene, mirrored)
    assert "worlds/kaihou/assets/gate.png" in html


def test_create_journal_returns_uuid():
    relay = FakeJournalRelay()
    uuid = create_journal(relay, {"id": 1, "title": "Scene"}, "<p>html</p>")
    assert uuid == "JournalEntry.new1"


def test_create_journal_raises_relay_error_on_failure():
    relay = FakeJournalRelay()
    relay.fail = True
    with pytest.raises(RelayError):
        create_journal(relay, {"id": 1, "title": "Scene"}, "<p>html</p>")


def test_update_journal_succeeds_for_existing_uuid():
    relay = FakeJournalRelay()
    uuid = create_journal(relay, {"id": 1, "title": "Scene"}, "<p>html</p>")
    update_journal(relay, uuid, "<p>updated</p>")
    assert relay.journals[uuid] == "<updated>"


def test_update_journal_raises_relay_error_on_failure():
    relay = FakeJournalRelay()
    relay.fail = True
    with pytest.raises(RelayError):
        update_journal(relay, "JournalEntry.missing", "<p>html</p>")
