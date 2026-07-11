# backend/gm_dashboard/clock_scan.py
from __future__ import annotations

import re
from pathlib import Path

import psycopg2.extras

H2_RE = re.compile(r"^##\s+(.+?)\s*$")
TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
META_SECTIONS = {"How To Use A Clock", "Clock Review After Every Session"}


def parse_clocks_file(text: str) -> list[dict]:
    lines = text.splitlines()
    section_starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        match = H2_RE.match(line)
        if match:
            section_starts.append((i, match.group(1).strip()))

    clocks: list[dict] = []
    for idx, (start, name) in enumerate(section_starts):
        if name in META_SECTIONS:
            continue
        end = section_starts[idx + 1][0] if idx + 1 < len(section_starts) else len(lines)
        body_lines = lines[start + 1 : end]

        segments = 0
        in_table = False
        for line in body_lines:
            if line.strip().startswith("| Segment "):
                in_table = True
                continue
            if in_table and set(line.strip()) <= {"|", "-", " ", ":"}:
                continue
            if in_table:
                if not TABLE_ROW_RE.match(line):
                    in_table = False
                    continue
                segments += 1

        description = "\n".join(body_lines).strip()
        clocks.append({"name": name, "segments": segments, "description": description})

    return clocks


def scan_clocks(vault_root: Path, cur, dry_run: bool = False) -> dict:
    clocks_path = (
        vault_root
        / "Campaign Management"
        / "01 - Live"
        / "Current Arc"
        / "The Training Arc"
        / "_Play Aids"
        / "Clocks and Beats.md"
    )
    scanned = 0
    new = 0
    duplicate_pending = 0
    review_ids: list[str] = []

    if not clocks_path.exists():
        return {"scanned": 0, "new": 0, "duplicate_pending": 0, "review_ids": []}

    for clock in parse_clocks_file(clocks_path.read_text()):
        scanned += 1
        cur.execute(
            """
            SELECT id FROM sync_reviews
            WHERE review_type = 'clock_import'
              AND review_status = 'pending'
              AND proposed_changes ->> 'name' = %s
            """,
            (clock["name"],),
        )
        if cur.fetchone():
            duplicate_pending += 1
            continue

        new += 1
        if dry_run:
            continue

        proposed_changes = {
            "name": clock["name"],
            "description": clock["description"],
            "kind": "progress",
            "segments": max(clock["segments"], 1),
            "filled": 0,
        }
        cur.execute(
            """
            INSERT INTO sync_reviews (
              review_type, source_surface, target_surface, target_type, target_id,
              base_version, current_version, proposed_changes, conflict_flags,
              review_status
            )
            VALUES (
              'clock_import', 'vault', 'postgres', 'clock', '',
              '', '', %(proposed_changes)s, '[]', 'pending'
            )
            RETURNING id
            """,
            {"proposed_changes": psycopg2.extras.Json(proposed_changes)},
        )
        review_ids.append(str(cur.fetchone()["id"]))

    return {"scanned": scanned, "new": new, "duplicate_pending": duplicate_pending, "review_ids": review_ids}
