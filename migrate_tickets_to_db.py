#!/usr/bin/env python3
"""Stage Markdown ticket imports through sync_reviews.

Usage:
  python migrate_tickets_to_db.py          # dry run: show parsed ticket files
  python migrate_tickets_to_db.py --apply  # create ticket_import sync_reviews

This script deliberately does not delete Markdown ticket files. Accepted reviews
can later be applied through /api/sync/reviews/{id}/apply.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from gm_dashboard.tickets_router import (  # noqa: E402
    _mapping_rows,
    _parse_ticket_file,
    _ticket_dir,
    _vault_root,
    stage_ticket_import_reviews,
)


def dry_run() -> None:
    vault_root = _vault_root()
    mapping = _mapping_rows(vault_root)
    paths = sorted(_ticket_dir(vault_root).glob("*.md"))
    print(f"Found {len(paths)} ticket .md files in {_ticket_dir(vault_root)}\n")
    for path in paths:
        try:
            ticket = _parse_ticket_file(path, vault_root, mapping)
        except ValueError as exc:
            print(f"  SKIP {path.name}: {exc}")
            continue
        print(
            "  OK  "
            f"{path.name} -> {ticket['id']!r} "
            f"[classification={ticket['classification'] or 'unmapped'}, "
            f"target_epic={ticket['target_epic'] or 'unmapped'}, "
            f"lane={ticket['lane']}]"
        )
    print("\nDry run complete. Pass --apply to create pending ticket_import reviews.")
    print("Markdown ticket files will not be deleted.")


def main(apply: bool) -> None:
    if not apply:
        dry_run()
        return
    result = stage_ticket_import_reviews()
    print(f"review_type: {result['review_type']}")
    print(f"found: {result['found']}")
    print(f"created: {len(result['created'])}")
    print(f"skipped: {len(result['skipped'])}")
    print(f"errors: {len(result['errors'])}")
    print(f"source_files_deleted: {result['source_files_deleted']}")
    for item in result["created"]:
        print(f"  CREATE review {item['review_id']} for {item['ticket_id']}")
    for item in result["skipped"]:
        print(f"  SKIP existing pending review {item['review_id']} for {item['ticket_id']}")
    for error in result["errors"]:
        print(f"  ERROR {error}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
