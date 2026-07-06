from __future__ import annotations

import pytest

from gm_dashboard.foundry_actors import create_actor, fetch_actor_stats, render_npc_actor_payload
from gm_dashboard.relay_client import RelayError


class FakeActorRelay:
    def __init__(self):
        self.actors: dict[str, dict] = {}
        self.fail_create = False
        self.last_create_payload: dict | None = None

    def execute_js(self, script: str) -> dict:
        if self.fail_create:
            return {"ok": False, "error": "create failed"}
        uuid = "Actor.fake123"
        self.actors[uuid] = {"system": {"abilities": {"str": {"value": 12}, "dex": {"value": 18}}}}
        return {"ok": True, "uuid": uuid}

    def get(self, uuid: str) -> dict:
        return self.actors[uuid]


def test_render_npc_actor_payload_maps_abilities_and_naruto_stats():
    npc = {
        "name": "Hayai",
        "img_path": "Lore/Assets/NPCs/Hayai.png",
        "stats": {
            "abilities": {"str": 12, "dex": 18},
            "naruto_stats": {"actionPoints": 0, "reputation": 1},
        },
    }
    payload = render_npc_actor_payload(npc)
    assert payload["name"] == "Hayai"
    assert payload["img"] == "Lore/Assets/NPCs/Hayai.png"
    assert payload["type"] == "npc"
    assert payload["system"]["abilities"]["str"] == {"value": 12}
    assert payload["system"]["naruto_stats"]["reputation"] == 1


def test_render_npc_actor_payload_handles_missing_stats():
    npc = {"name": "Bare NPC", "img_path": None}
    payload = render_npc_actor_payload(npc)
    assert payload["name"] == "Bare NPC"
    assert payload["img"] == ""
    assert payload["system"]["abilities"] == {}
    assert payload["system"]["naruto_stats"] == {}


def test_create_actor_returns_uuid_on_success():
    relay = FakeActorRelay()
    uuid = create_actor(relay, {"name": "Hayai"})
    assert uuid == "Actor.fake123"


def test_create_actor_raises_relay_error_on_failure():
    relay = FakeActorRelay()
    relay.fail_create = True
    with pytest.raises(RelayError):
        create_actor(relay, {"name": "Hayai"})


def test_fetch_actor_stats_extracts_abilities_and_naruto_stats():
    relay = FakeActorRelay()
    uuid = create_actor(relay, {"name": "Hayai"})
    stats = fetch_actor_stats(relay, uuid)
    assert stats == {"abilities": {"str": 12, "dex": 18}, "naruto_stats": {}}
