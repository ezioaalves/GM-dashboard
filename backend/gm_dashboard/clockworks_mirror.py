from __future__ import annotations

import json
import secrets
from typing import Any

from .relay_client import RelayClient, load_relay_client

SETTING_KEY = "fvtt-clock-works.clockList"


class MirrorError(Exception):
    """Raised when a Clock-Works mirror operation cannot complete."""


def render_clockworks_entry(clock: dict, foundry_id: str, list_position: int = 0) -> dict:
    return {
        "id": foundry_id,
        "name": clock["name"],
        "max": clock["segments"],
        "value": clock["filled"],
        "listPosition": list_position,
        "persist": True,
    }


def new_foundry_id() -> str:
    return f"clock-works-{secrets.token_hex(8)}"


def _find_setting_uuid(client: RelayClient) -> str:
    for candidate in client.search("clockList"):
        uuid = str(candidate.get("uuid", ""))
        if uuid.startswith("Setting.") or candidate.get("documentType") == "Setting":
            return uuid
    raise MirrorError(f"Setting document for {SETTING_KEY} not found via relay /search")


def read_clock_list(client: RelayClient) -> tuple[str, dict[str, Any]]:
    setting_uuid = _find_setting_uuid(client)
    data = client.get(setting_uuid)
    raw = data.get("value") or "{}"
    if isinstance(raw, str):
        return setting_uuid, json.loads(raw)
    if isinstance(raw, dict):
        return setting_uuid, raw
    raise MirrorError("Clock-Works clockList setting has an unsupported value shape")


def push_entry(client: RelayClient, entry: dict) -> None:
    setting_uuid, clock_list = read_clock_list(client)
    existing = clock_list.get(entry["id"], {})
    clock_list[entry["id"]] = {**existing, **entry}
    client.update(setting_uuid, {"value": json.dumps(clock_list)})


def remove_entry(client: RelayClient, foundry_id: str) -> None:
    setting_uuid, clock_list = read_clock_list(client)
    if foundry_id in clock_list:
        del clock_list[foundry_id]
        client.update(setting_uuid, {"value": json.dumps(clock_list)})


def check_drift(client: RelayClient, mirrored: list[dict], env: str) -> list[dict]:
    _, clock_list = read_clock_list(client)
    verdicts = []
    id_col = f"foundry_clock_id_{env}"
    for clock in mirrored:
        entry = clock_list.get(clock[id_col])
        if entry is None:
            verdicts.append({"clock_id": str(clock["id"]), "kind": "missing_mirror"})
            continue
        drift = {}
        if entry.get("value") != clock["filled"]:
            drift["value"] = {"engine": clock["filled"], "foundry": entry.get("value")}
        if entry.get("max") != clock["segments"]:
            drift["max"] = {"engine": clock["segments"], "foundry": entry.get("max")}
        if entry.get("name") != clock["name"]:
            drift["name"] = {"engine": clock["name"], "foundry": entry.get("name")}
        if drift:
            verdicts.append({"clock_id": str(clock["id"]), "kind": "value_drift", "fields": drift})
    return verdicts
