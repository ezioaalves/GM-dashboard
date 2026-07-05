"""Spike: can the relay read/write the Clock-Works clockList world setting?

Run manually with the selected world open in Foundry:
    cd "Creation Zone/gm-dashboard" && python3 backend/scripts/spike_clockworks_setting.py --env prod

PASS criteria (all three):
  1. A Setting document uuid for key 'fvtt-clock-works.clockList' is discoverable.
  2. /get returns its current value.
  3. /update writes a modified value AND the new clock is visible in the
     Clock-Works sidebar (after re-render or F5) in the selected world.

Record the outcome in docs/superpowers/plans/2026-07-04-gm-dashboard-clock-engine.md
under Task 8 as a checked note before starting Task 9.
"""
from __future__ import annotations

import sys
from argparse import ArgumentParser

sys.path.insert(0, "backend")

from gm_dashboard.clockworks_mirror import MirrorError, read_clock_list, remove_entry, push_entry  # noqa: E402
from gm_dashboard.relay_client import RelayError, load_relay_client  # noqa: E402

SETTING_KEY = "fvtt-clock-works.clockList"


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--env", choices=("test", "prod"), default="test")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    try:
        client = load_relay_client(args.env)
    except RelayError as exc:
        print(f"FAIL (setup): {exc}")
        return 1

    print("1) Reading Clock-Works clockList...")
    try:
        setting_uuid, current = read_clock_list(client)
    except (RelayError, MirrorError) as exc:
        print(f"FAIL (read): {exc}")
        return 1
    print(f"   source: {setting_uuid}")
    print(f"   current entries: {len(current)}")

    spike_id = "clock-works-spike0001"
    if args.cleanup:
        print("2) Removing the spike clock if present...")
        try:
            remove_entry(client, spike_id)
            _, readback = read_clock_list(client)
        except (RelayError, MirrorError) as exc:
            print(f"FAIL (cleanup): {exc}")
            return 1
        if spike_id in readback:
            print("FAIL: cleanup did not round-trip")
            return 1
        print("   cleanup round-trip OK.")
        return 0

    print("2) Writing a spike clock...")
    try:
        push_entry(client, {
        "id": spike_id, "name": "SPIKE - delete me", "max": 4, "value": 1,
        "listPosition": 999, "persist": True,
        })
        _, readback = read_clock_list(client)
    except (RelayError, MirrorError) as exc:
        print(f"FAIL (write): {exc}")
        return 1
    if spike_id not in readback:
        print("FAIL: write did not round-trip")
        return 1
    print(f"   round-trip OK. Now CHECK THE {args.env.upper()} WORLD UI: does 'SPIKE - delete me'")
    print("   appear in the Clock-Works sidebar (re-render or F5)?")
    print(f"   Clean up: re-run with --env {args.env} --cleanup or delete the clock in Foundry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
