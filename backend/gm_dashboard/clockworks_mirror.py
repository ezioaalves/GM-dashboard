from __future__ import annotations

import json
import secrets
from typing import Any

from .relay_client import RelayClient, load_relay_client

ACTIVE_MODULE_IDS = ("clock-works", "fvtt-clock-works")
SETTING_NAMESPACE = "fvtt-clock-works"
SETTING_KEY = f"{SETTING_NAMESPACE}.clockList"


class MirrorError(Exception):
    """Raised when a Clock-Works mirror operation cannot complete."""


def render_clockworks_entry(clock: dict, foundry_id: str, list_position: int = 0) -> dict:
    return {
        "id": foundry_id,
        "name": clock["name"],
        "size": clock["segments"],
        "filled": clock["filled"],
        "listPosition": list_position,
        "persist": True,
        "ownership": {"default": 3},
    }


def new_foundry_id() -> str:
    return f"clock-works-{secrets.token_hex(8)}"


def _find_setting_uuid(client: RelayClient) -> str:
    for candidate in client.search("clockList"):
        uuid = str(candidate.get("uuid", ""))
        if uuid.startswith("Setting.") or candidate.get("documentType") == "Setting":
            return uuid
    raise MirrorError(f"Setting document for {SETTING_KEY} not found via relay /search")


def _read_clock_list_via_js(client: RelayClient) -> dict[str, Any]:
    module_ids = json.dumps(list(ACTIVE_MODULE_IDS))
    script = f"""
const moduleIds = {module_ids};
let moduleId = null;
for (const candidate of moduleIds) {{
  const mod = game.modules.get(candidate);
  if (mod?.active) {{
    moduleId = candidate;
    break;
  }}
}}
if (!moduleId) {{
  return {{ ok: false, error: "Clock-Works module is not active" }};
}}
let value = game.settings.get("{SETTING_NAMESPACE}", "clockList") ?? {{}};
if (typeof value === "string") value = JSON.parse(value || "{{}}");
return {{ ok: true, moduleId, value }};
"""
    result = client.execute_js(script)
    if not result.get("ok"):
        raise MirrorError(result.get("error") or "Clock-Works setting read failed via execute-js")
    value = result.get("value") or {}
    if isinstance(value, dict):
        return value
    raise MirrorError("Clock-Works clockList setting has an unsupported value shape")


def _write_clock_list_via_js(client: RelayClient, clock_list: dict[str, Any]) -> None:
    payload = json.dumps(clock_list)
    module_ids = json.dumps(list(ACTIVE_MODULE_IDS))
    script = f"""
const moduleIds = {module_ids};
let moduleId = null;
for (const candidate of moduleIds) {{
  const mod = game.modules.get(candidate);
  if (mod?.active) {{
    moduleId = candidate;
    break;
  }}
}}
if (!moduleId) {{
  return {{ ok: false, error: "Clock-Works module is not active" }};
}}
const value = {payload};
await game.settings.set("{SETTING_NAMESPACE}", "clockList", value);
return {{ ok: true, moduleId, count: Object.keys(value).length }};
"""
    result = client.execute_js(script)
    if not result.get("ok"):
        raise MirrorError(result.get("error") or "Clock-Works setting write failed via execute-js")


def _upsert_entry_via_macro(client: RelayClient, entry: dict) -> None:
    if not client.clockworks_macro_uuid:
        raise MirrorError("Clock-Works macro UUID is not configured")
    result = client.execute_macro(client.clockworks_macro_uuid, [{"entry": entry}])
    if not result.get("ok"):
        raise MirrorError(result.get("error") or "Clock-Works macro upsert failed")


def _remove_entry_via_macro(client: RelayClient, foundry_id: str) -> None:
    if not client.clockworks_macro_uuid:
        raise MirrorError("Clock-Works macro UUID is not configured")
    result = client.execute_macro(client.clockworks_macro_uuid, [{"removeId": foundry_id}])
    if not result.get("ok"):
        raise MirrorError(result.get("error") or "Clock-Works macro removal failed")


def read_clock_list(client: RelayClient) -> tuple[str, dict[str, Any]]:
    try:
        setting_uuid = _find_setting_uuid(client)
        data = client.get(setting_uuid)
        raw = data.get("value") or "{}"
        if isinstance(raw, str):
            return setting_uuid, json.loads(raw)
        if isinstance(raw, dict):
            return setting_uuid, raw
    except Exception:
        return "game.settings:fvtt-clock-works.clockList", _read_clock_list_via_js(client)
    raise MirrorError("Clock-Works clockList setting has an unsupported value shape")


def push_entry(client: RelayClient, entry: dict) -> None:
    if getattr(client, "clockworks_macro_uuid", ""):
        _upsert_entry_via_macro(client, entry)
        return
    setting_uuid, clock_list = read_clock_list(client)
    existing = clock_list.get(entry["id"], {})
    clock_list[entry["id"]] = {**existing, **entry}
    if setting_uuid.startswith("game.settings:"):
        _write_clock_list_via_js(client, clock_list)
    else:
        client.update(setting_uuid, {"value": json.dumps(clock_list)})


def remove_entry(client: RelayClient, foundry_id: str) -> None:
    if getattr(client, "clockworks_macro_uuid", ""):
        _remove_entry_via_macro(client, foundry_id)
        return
    setting_uuid, clock_list = read_clock_list(client)
    if foundry_id in clock_list:
        del clock_list[foundry_id]
        if setting_uuid.startswith("game.settings:"):
            _write_clock_list_via_js(client, clock_list)
        else:
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
        foundry_filled = entry.get("filled", entry.get("value"))
        foundry_size = entry.get("size", entry.get("max"))
        if foundry_filled != clock["filled"]:
            drift["value"] = {"engine": clock["filled"], "foundry": foundry_filled}
        if foundry_size != clock["segments"]:
            drift["max"] = {"engine": clock["segments"], "foundry": foundry_size}
        if entry.get("name") != clock["name"]:
            drift["name"] = {"engine": clock["name"], "foundry": entry.get("name")}
        if drift:
            verdicts.append({"clock_id": str(clock["id"]), "kind": "value_drift", "fields": drift})
    return verdicts
