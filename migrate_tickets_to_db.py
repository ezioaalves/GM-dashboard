#!/usr/bin/env python3
"""One-shot: seed Postgres tickets table from .md files, then delete them.

Usage:
  python migrate_tickets_to_db.py          # dry run: show what would be inserted
  python migrate_tickets_to_db.py --apply  # insert + delete on confirmation
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path

import psycopg2
import psycopg2.extras
import yaml

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@localhost:54329/kaihou_gm",
)

VAULT_ROOT = Path(__file__).parent.parent.parent  # walk up from gm-dashboard/
TICKETS_DIR = VAULT_ROOT / "Campaign Management/operational/tickets"
AUTOMATION_DIR = VAULT_ROOT / "Creation Zone/automation_scripts"
DASHBOARD_FILE = VAULT_ROOT / "Campaign Management/operational/operational-dashboard.md"

FILES_TO_DELETE_AFTER = [
    AUTOMATION_DIR / "validate_operational.py",
    AUTOMATION_DIR / "build_operational_dashboard.py",
    AUTOMATION_DIR / "seed_operational_from_todos.py",
    AUTOMATION_DIR / "operational_core.py",
    AUTOMATION_DIR / "tests/test_operational_core.py",
    AUTOMATION_DIR / "tests/test_validate_operational.py",
    AUTOMATION_DIR / "tests/test_build_operational_dashboard.py",
    AUTOMATION_DIR / "tests/test_seed_operational.py",
    DASHBOARD_FILE,
]


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return fm, body


def parse_ticket_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if not fm.get("id") or not fm.get("title"):
        print(f"  SKIP {path.name}: missing id or title")
        return None

    def ensure_list(v) -> list:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]

    return {
        "id": str(fm["id"]),
        "title": str(fm["title"]),
        "status": str(fm.get("status", "open")),
        "area": str(fm.get("area", "docs")),
        "priority": str(fm.get("priority", "med")),
        "stage": str(fm.get("stage", "next")),
        "parent_id": fm.get("parent_id") or None,
        "threads": ensure_list(fm.get("threads")),
        "depends_on": ensure_list(fm.get("depends_on")),
        "next_action": str(fm.get("next_action") or ""),
        "resume_note": str(fm.get("resume_note") or ""),
        "source": str(fm.get("source") or "manual"),
        "introduced": fm.get("introduced") or None,
        "closed": fm.get("closed") or None,
        "resolution": str(fm.get("resolution") or ""),
        "review_after": fm.get("review_after") or None,
        "body": body,
    }


def main(apply: bool) -> None:
    md_files = sorted(
        p for p in TICKETS_DIR.glob("*.md")
        if "_drafts" not in str(p)
    )
    print(f"Found {len(md_files)} ticket .md files in {TICKETS_DIR}\n")

    tickets = []
    for path in md_files:
        t = parse_ticket_file(path)
        if t:
            tickets.append((path, t))
            print(f"  OK  {path.name}  →  {t['id']!r}  [{t['stage']}]")

    print(f"\nReady to insert {len(tickets)} tickets into Postgres.")
    print(f"DATABASE_URL: {DATABASE_URL}\n")

    if not apply:
        print("Dry run complete. Pass --apply to write to DB and delete files.")
        return

    confirm = input(
        f"This will INSERT {len(tickets)} tickets and DELETE all .md source files\n"
        "and operational automation scripts. Type 'yes' to confirm: "
    )
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    inserted = 0
    skipped = 0
    error_paths = set()
    with conn.cursor() as cur:
        for path, t in tickets:
            try:
                cur.execute(
                    """
                    INSERT INTO tickets (
                      id, title, status, area, priority, stage, parent_id,
                      threads, depends_on, next_action, resume_note, source,
                      introduced, closed, resolution, review_after, body
                    ) VALUES (
                      %(id)s, %(title)s, %(status)s, %(area)s, %(priority)s, %(stage)s,
                      %(parent_id)s, %(threads)s, %(depends_on)s, %(next_action)s,
                      %(resume_note)s, %(source)s, %(introduced)s, %(closed)s,
                      %(resolution)s, %(review_after)s, %(body)s
                    ) ON CONFLICT (id) DO NOTHING
                    """,
                    t,
                )
                if cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1
                    print(f"  SKIP (already exists): {t['id']}")
            except Exception as exc:
                print(f"  ERROR inserting {t['id']}: {exc}")
                error_paths.add(path)
    conn.close()
    print(f"\nInserted {inserted} tickets ({skipped} skipped — already in DB).")

    # Delete source .md files
    print("\nDeleting .md ticket files...")
    for path, _ in tickets:
        if path not in error_paths:
            path.unlink()
            print(f"  deleted {path.name}")
        else:
            print(f"  KEPT (insert failed): {path.name}")

    # Delete automation scripts
    print("\nDeleting operational automation scripts...")
    for path in FILES_TO_DELETE_AFTER:
        if path.exists():
            path.unlink()
            print(f"  deleted {path.relative_to(VAULT_ROOT)}")
        else:
            print(f"  not found (skipped): {path.relative_to(VAULT_ROOT)}")

    print("\nMigration complete.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
