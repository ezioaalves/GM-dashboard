"""Spike: can the relay read/write the Clock-Works clockList world setting?

Run manually with the LOCAL TEST world open in Foundry (localhost:30000):
    cd "Creation Zone/gm-dashboard" && python3 backend/scripts/spike_clockworks_setting.py

PASS criteria (all three):
  1. A Setting document uuid for key 'fvtt-clock-works.clockList' is discoverable.
  2. /get returns its current value.
  3. /update writes a modified value AND the new clock is visible in the
     Clock-Works sidebar (after re-render or F5) in the test world.

Record the outcome in docs/superpowers/plans/2026-07-04-gm-dashboard-clock-engine.md
under Task 8 as a checked note before starting Task 9.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "backend")

from gm_dashboard.relay_client import RelayError, load_relay_client  # noqa: E402

SETTING_KEY = "fvtt-clock-works.clockList"


def main() -> int:
    try:
        client = load_relay_client("test")
    except RelayError as exc:
        print(f"FAIL (setup): {exc}")
        return 1

    print("1) Searching for the Setting document...")
    setting_uuid = None
    for candidate in client.search("clockList"):
        if candidate.get("documentType") == "Setting" or "Setting." in str(candidate.get("uuid", "")):
            setting_uuid = candidate["uuid"]
            break
    if setting_uuid is None:
        print("   /search did not surface it; try /get on Setting uuids from a local DB dump:")
        print("   grep clockList ~/Documents/foundry/foundrydata/Data/worlds/<world>/data/settings.db")
        return 1
    print(f"   found: {setting_uuid}")

    print("2) Reading current value...")
    data = client.get(setting_uuid)
    print(f"   raw: {json.dumps(data)[:300]}")
    current = json.loads(data.get("value") or "{}")

    print("3) Writing a spike clock...")
    spike_id = "clock-works-spike0001"
    current[spike_id] = {
        "id": spike_id, "name": "SPIKE - delete me", "max": 4, "value": 1,
        "listPosition": 999, "persist": True,
    }
    client.update(setting_uuid, {"value": json.dumps(current)})
    readback = json.loads(client.get(setting_uuid).get("value") or "{}")
    if spike_id not in readback:
        print("FAIL: write did not round-trip")
        return 1
    print("   round-trip OK. Now CHECK THE TEST WORLD UI: does 'SPIKE - delete me'")
    print("   appear in the Clock-Works sidebar (re-render or F5)?")
    print("   Clean up: re-run with CLEANUP=1 or delete the clock in Foundry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
