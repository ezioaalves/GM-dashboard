from __future__ import annotations

import json

from .relay_client import RelayError

NPC_ABILITY_KEYS = ("str", "dex", "con", "int", "wis", "cha")


def render_npc_actor_payload(npc: dict) -> dict:
    stats = npc.get("stats") or {}
    abilities = stats.get("abilities") or {}
    naruto_stats = stats.get("naruto_stats") or {}
    return {
        "name": npc["name"],
        "type": "npc",
        "img": npc.get("img_path") or "",
        "system": {
            "abilities": {
                key: {"value": abilities[key]} for key in NPC_ABILITY_KEYS if key in abilities
            },
            "naruto_stats": naruto_stats,
        },
    }


def create_actor(client, payload: dict) -> str:
    script = f"""
const data = {json.dumps(payload)};
const actor = await Actor.implementation.create(data);
return {{ ok: true, uuid: actor.uuid }};
"""
    result = client.execute_js(script)
    if not result.get("ok"):
        raise RelayError(result.get("error") or "actor creation failed via execute-js")
    return result["uuid"]


def fetch_actor_stats(client, foundry_actor_id: str) -> dict:
    data = client.get(foundry_actor_id)
    system = data.get("system") or {}
    abilities_raw = system.get("abilities") or {}
    abilities = {
        key: value.get("value")
        for key, value in abilities_raw.items()
        if key in NPC_ABILITY_KEYS and isinstance(value, dict)
    }
    return {"abilities": abilities, "naruto_stats": system.get("naruto_stats") or {}}
