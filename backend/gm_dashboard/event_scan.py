# backend/gm_dashboard/event_scan.py
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import psycopg2.extras

H2_RE = re.compile(r"^##\s+(.+?)\s*$")
META_SECTIONS = {"Live Pressures", "How To Use An Event"}

EVENTS_REL_PATH = (
    "Campaign Management/01 - Live/Current Arc/The Training Arc/_Play Aids/Event Library.md"
)


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_events_file(text: str) -> list[dict]:
    lines = text.splitlines()
    section_starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        match = H2_RE.match(line)
        if match:
            section_starts.append((i, match.group(1).strip()))

    modules: list[dict] = []
    for idx, (start, title) in enumerate(section_starts):
        if title in META_SECTIONS:
            continue
        end = section_starts[idx + 1][0] if idx + 1 < len(section_starts) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()

        trigger_match = re.search(r"### Trigger\s*\n\n(.+?)(\n\n|\Z)", body, re.DOTALL)
        purpose = trigger_match.group(1).strip().splitlines()[0] if trigger_match else ""

        modules.append({"title": title, "body": body, "purpose": purpose})

    return modules


def _matching_clock_names(cur, title: str) -> list[str]:
    cur.execute("SELECT name FROM clocks")
    names = [row["name"] for row in cur.fetchall()]
    lowered = title.lower()
    return [name for name in names if name.lower() in lowered or lowered.startswith(name.lower().split(" - ")[0])]


def scan_events(vault_root: Path, cur, dry_run: bool = False) -> dict:
    events_path = vault_root / EVENTS_REL_PATH
    scanned = 0
    new = 0
    changed = 0
    unchanged = 0
    review_ids: list[str] = []

    if not events_path.exists():
        return {"scanned": 0, "new": 0, "changed": 0, "unchanged": 0, "review_ids": []}

    for module in parse_events_file(events_path.read_text()):
        scanned += 1
        source_hash = compute_hash(module["body"])
        source_path = f"{EVENTS_REL_PATH}#{module['title']}"

        cur.execute("SELECT id, source_hash FROM scenes WHERE source_path = %s", (source_path,))
        existing = cur.fetchone()

        if existing is not None and existing["source_hash"] == source_hash:
            unchanged += 1
            continue

        cur.execute(
            """
            SELECT id FROM sync_reviews
            WHERE review_type = 'scene_import'
              AND review_status = 'pending'
              AND proposed_changes ->> 'source_path' = %s
            """,
            (source_path,),
        )
        if cur.fetchone():
            continue

        clock_names = _matching_clock_names(cur, module["title"])
        if existing is None:
            new += 1
        else:
            changed += 1

        if dry_run:
            continue

        proposed_changes = {
            "title": module["title"],
            "placement": "backlog",
            "scene_type": "soft",
            "purpose": module["purpose"],
            "body": module["body"],
            "clock": clock_names,
            "source_path": source_path,
            "source_hash": source_hash,
        }
        cur.execute(
            """
            INSERT INTO sync_reviews (
              review_type, source_surface, target_surface, target_type, target_id,
              base_version, current_version, proposed_changes, conflict_flags,
              review_status
            )
            VALUES (
              'scene_import', 'vault', 'postgres', 'scene', %(target_id)s,
              '', %(current_version)s, %(proposed_changes)s, '[]', 'pending'
            )
            RETURNING id
            """,
            {
                "target_id": str(existing["id"]) if existing else "",
                "current_version": source_hash,
                "proposed_changes": psycopg2.extras.Json(proposed_changes),
            },
        )
        review_ids.append(str(cur.fetchone()["id"]))

    return {"scanned": scanned, "new": new, "changed": changed, "unchanged": unchanged, "review_ids": review_ids}
