from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg2.extras

from . import services


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_session_log(text: str, path: Path) -> dict | None:
    fm, body = services.split_frontmatter(text, path)
    number = fm.get("session")
    if not isinstance(number, int):
        return None

    threads = fm.get("threads") or {}
    threads_touched = [
        str(t)
        for t in (
            list(threads.get("advanced") or [])
            + list(threads.get("planted") or [])
            + list(threads.get("resolved") or [])
        )
    ]

    session_fields = {
        "number": number,
        "name": str(fm.get("title", path.stem)),
        "date": str(fm.get("date")) if fm.get("date") else None,
        "summary": services.extract_section(body, "What happened"),
    }
    session_note_fields = {
        "scenes": services.bullets_from_section(body, "Notable moments"),
        "npcs_present": [str(n) for n in (fm.get("npcs_present") or [])],
        "clues_discovered": services.bullets_from_section(body, "Clues discovered"),
        "threads_touched": threads_touched,
        "unresolved_questions": services.bullets_from_section(body, "Unresolved questions"),
        "next_session_hook": services.extract_section(body, "Hook for next session"),
        "memory": services.extract_section(body, "Continuity notes"),
        "markdown": text,
    }
    return {"session": session_fields, "session_note": session_note_fields}


def scan_sessions(vault_root: Path, cur, dry_run: bool = False) -> dict:
    logs_dir = vault_root / services.SESSION_LOGS
    scanned = 0
    new = 0
    changed = 0
    unchanged = 0
    skipped = 0
    review_ids: list[str] = []

    if not logs_dir.exists():
        return {"scanned": 0, "new": 0, "changed": 0, "unchanged": 0, "skipped": 0, "review_ids": []}

    for path in sorted(logs_dir.glob("*.md")):
        if path.name.endswith(".secret.md") or "_drafts" in path.parts:
            continue
        scanned += 1
        text = path.read_text()
        parsed = parse_session_log(text, path)
        if parsed is None:
            skipped += 1
            continue

        source_path = services.relative(vault_root, path)
        source_hash = compute_hash(text)

        cur.execute(
            "SELECT id, source_hash FROM sessions WHERE number = %s",
            (parsed["session"]["number"],),
        )
        existing = cur.fetchone()

        if existing is not None and existing["source_hash"] == source_hash:
            unchanged += 1
            continue

        cur.execute(
            """
            SELECT id FROM sync_reviews
            WHERE review_type = 'session_import'
              AND review_status = 'pending'
              AND proposed_changes ->> 'source_path' = %s
            """,
            (source_path,),
        )
        if cur.fetchone():
            continue

        if existing is None:
            new += 1
        else:
            changed += 1

        if dry_run:
            continue

        proposed_changes = {
            "session": parsed["session"],
            "session_note": parsed["session_note"],
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
              'session_import', 'vault', 'postgres', 'session', %(target_id)s,
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

    return {
        "scanned": scanned,
        "new": new,
        "changed": changed,
        "unchanged": unchanged,
        "skipped": skipped,
        "review_ids": review_ids,
    }
