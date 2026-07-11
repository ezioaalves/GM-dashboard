# backend/gm_dashboard/risk_scan.py
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import psycopg2.extras

TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_risks_file(text: str) -> list[dict]:
    lines = text.splitlines()
    rows: list[dict] = []
    in_table = False
    for line in lines:
        if line.strip().startswith("| Risk "):
            in_table = True
            continue
        if in_table and set(line.strip()) <= {"|", "-", " ", ":"}:
            continue
        if in_table:
            if not TABLE_ROW_RE.match(line):
                break
            cells = _split_row(line)
            if len(cells) != 5:
                continue
            risk, likelihood, mitigation, contingency, last_reviewed = cells
            rows.append(
                {
                    "title": risk,
                    "likelihood": likelihood.lower(),
                    "mitigation": mitigation,
                    "contingency": contingency,
                    "last_reviewed_date": last_reviewed if DATE_RE.match(last_reviewed) else None,
                }
            )
    return rows


def _resolve_session_number(cur, last_reviewed_date: str | None) -> int | None:
    if not last_reviewed_date:
        return None
    cur.execute(
        "SELECT number FROM sessions WHERE date <= %s ORDER BY date DESC LIMIT 1",
        (last_reviewed_date,),
    )
    row = cur.fetchone()
    return row["number"] if row else None


def scan_risks(vault_root: Path, cur, dry_run: bool = False) -> dict:
    risks_path = vault_root / "Campaign Management" / "operational" / "risks.md"
    scanned = 0
    new = 0
    duplicate_pending = 0
    review_ids: list[str] = []

    if not risks_path.exists():
        return {"scanned": 0, "new": 0, "duplicate_pending": 0, "review_ids": []}

    rows = parse_risks_file(risks_path.read_text())
    rel_path = "Campaign Management/operational/risks.md"

    for row in rows:
        scanned += 1
        cur.execute(
            """
            SELECT id FROM sync_reviews
            WHERE review_type = 'risk_import'
              AND review_status = 'pending'
              AND proposed_changes ->> 'title' = %s
            """,
            (row["title"],),
        )
        if cur.fetchone():
            duplicate_pending += 1
            continue

        new += 1
        if dry_run:
            continue

        proposed_changes = {
            "title": row["title"],
            "description": "",
            "likelihood": row["likelihood"],
            "mitigation": row["mitigation"],
            "contingency": row["contingency"],
            "status": "open",
            "last_reviewed_session": _resolve_session_number(cur, row["last_reviewed_date"]),
            "source_path": rel_path,
        }
        cur.execute(
            """
            INSERT INTO sync_reviews (
              review_type, source_surface, target_surface, target_type, target_id,
              base_version, current_version, proposed_changes, conflict_flags,
              review_status
            )
            VALUES (
              'risk_import', 'vault', 'postgres', 'risk', '',
              '', '', %(proposed_changes)s, '[]', 'pending'
            )
            RETURNING id
            """,
            {"proposed_changes": psycopg2.extras.Json(proposed_changes)},
        )
        review_ids.append(str(cur.fetchone()["id"]))

    return {"scanned": scanned, "new": new, "duplicate_pending": duplicate_pending, "review_ids": review_ids}
