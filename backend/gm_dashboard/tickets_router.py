from __future__ import annotations

import re
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yaml

from .db.get_db import get_connection

router = APIRouter()

VALID_AREAS = {"lore", "mechanics", "foundry", "cosmetics", "skills", "docs", "housekeeping"}
VALID_STAGES = {"now", "next", "deferred", "done"}
VALID_STATUSES = {"open", "in_progress", "blocked", "done", "dropped"}
VALID_PRIORITIES = {"high", "med", "low"}


class TicketResponse(BaseModel):
    id: str
    title: str
    status: str
    area: str
    priority: str
    stage: str
    parent_id: Optional[str] = None
    threads: list[str] = []
    depends_on: list[str] = []
    next_action: str = ""
    resume_note: str = ""
    source: str = "manual"
    introduced: Optional[date] = None
    closed: Optional[date] = None
    resolution: str = ""
    review_after: Optional[date] = None
    lane: str = "next"
    classification: str = ""
    target_epic: str = ""
    source_path: str = ""
    source_hash: str = ""
    source_mtime: Optional[datetime] = None
    review_status: str = "accepted"
    body: str = ""


class TicketCreate(BaseModel):
    id: Optional[str] = None
    title: str
    status: str = "open"
    area: str
    priority: str = "med"
    stage: str = "next"
    parent_id: Optional[str] = None
    threads: list[str] = []
    depends_on: list[str] = []
    next_action: str = ""
    resume_note: str = ""
    source: str = "manual"
    introduced: Optional[date] = None
    closed: Optional[date] = None
    resolution: str = ""
    review_after: Optional[date] = None
    lane: str = "next"
    classification: str = ""
    target_epic: str = ""
    source_path: str = ""
    source_hash: str = ""
    source_mtime: Optional[datetime] = None
    review_status: str = "accepted"
    body: str = ""


class TicketUpdate(BaseModel):
    title: str
    status: str
    area: str
    priority: str
    stage: str
    parent_id: Optional[str] = None
    threads: list[str] = []
    depends_on: list[str] = []
    next_action: str = ""
    resume_note: str = ""
    source: str = "manual"
    introduced: Optional[date] = None
    closed: Optional[date] = None
    resolution: str = ""
    review_after: Optional[date] = None
    lane: str = "next"
    classification: str = ""
    target_epic: str = ""
    source_path: str = ""
    source_hash: str = ""
    source_mtime: Optional[datetime] = None
    review_status: str = "accepted"
    body: str = ""


class TicketStagePatch(BaseModel):
    stage: str


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def _vault_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _ticket_dir(vault_root: Path) -> Path:
    return vault_root / "Campaign Management" / "operational" / "tickets"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    return yaml.safe_load(parts[1]) or {}, parts[2].strip()


def _ensure_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _source_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _mapping_rows(vault_root: Path) -> dict[str, dict[str, str]]:
    path = vault_root / "docs" / "superpowers" / "system-definition" / "12-backlog-mapping.md"
    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    in_ticket_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "## Operational Tickets":
            in_ticket_table = True
            continue
        if in_ticket_table and line.startswith("## "):
            break
        if not in_ticket_table or not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        ticket_id = cells[0].strip("`")
        rows[ticket_id] = {
            "classification": cells[1].strip("`"),
            "target_epic": cells[2],
            "notes": cells[3],
        }
    return rows


def _lane_for(ticket: dict, classification: str) -> str:
    stage = str(ticket.get("stage") or "").lower()
    if stage in VALID_STAGES:
        return stage
    if classification == "deferred":
        return "deferred"
    if classification in {"historical", "superseded", "external-reference"}:
        return "deferred"
    return "next"


def _parse_ticket_file(path: Path, vault_root: Path, mapping: dict[str, dict[str, str]]) -> dict:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    if not fm.get("id") or not fm.get("title"):
        raise ValueError(f"{path.name}: missing id or title")
    ticket_id = str(fm["id"])
    mapped = mapping.get(ticket_id, {})
    classification = mapped.get("classification", "")
    ticket = {
        "id": ticket_id,
        "title": str(fm["title"]),
        "status": str(fm.get("status", "open")),
        "area": str(fm.get("area", "docs")),
        "priority": str(fm.get("priority", "med")),
        "stage": str(fm.get("stage", "next")),
        "parent_id": fm.get("parent_id") or None,
        "threads": _ensure_list(fm.get("threads")),
        "depends_on": _ensure_list(fm.get("depends_on")),
        "next_action": str(fm.get("next_action") or ""),
        "resume_note": str(fm.get("resume_note") or ""),
        "source": "markdown_ticket",
        "introduced": fm.get("introduced") or None,
        "closed": fm.get("closed") or None,
        "resolution": str(fm.get("resolution") or ""),
        "review_after": fm.get("review_after") or None,
        "lane": "",
        "classification": classification,
        "target_epic": mapped.get("target_epic", ""),
        "source_path": str(path.relative_to(vault_root)),
        "source_hash": _source_hash(text),
        "source_mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "review_status": "pending",
        "body": body,
    }
    ticket["lane"] = _lane_for(ticket, classification)
    return ticket


def _row_to_dict(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "area": row["area"],
        "priority": row["priority"],
        "stage": row["stage"],
        "parent_id": row["parent_id"],
        "threads": list(row["threads"] or []),
        "depends_on": list(row["depends_on"] or []),
        "next_action": row["next_action"] or "",
        "resume_note": row["resume_note"] or "",
        "source": row["source"] or "manual",
        "introduced": row["introduced"],
        "closed": row["closed"],
        "resolution": row["resolution"] or "",
        "review_after": row["review_after"],
        "lane": row.get("lane") or row["stage"] or "next",
        "classification": row.get("classification") or "",
        "target_epic": row.get("target_epic") or "",
        "source_path": row.get("source_path") or "",
        "source_hash": row.get("source_hash") or "",
        "source_mtime": row.get("source_mtime"),
        "review_status": row.get("review_status") or "accepted",
        "body": row["body"] or "",
    }


@router.post("/tickets/import/review", status_code=201)
def stage_ticket_import_reviews() -> dict:
    vault_root = _vault_root()
    mapping = _mapping_rows(vault_root)
    tickets: list[dict] = []
    errors: list[str] = []
    for path in sorted(_ticket_dir(vault_root).glob("*.md")):
        try:
            tickets.append(_parse_ticket_file(path, vault_root, mapping))
        except ValueError as exc:
            errors.append(str(exc))

    conn = get_connection()
    created: list[dict] = []
    skipped: list[dict] = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for ticket in tickets:
                cur.execute(
                    """
                    SELECT id, review_status
                    FROM sync_reviews
                    WHERE review_type = 'ticket_import'
                      AND target_type = 'ticket'
                      AND target_id = %s
                      AND current_version = %s
                      AND review_status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (ticket["id"], ticket["source_hash"]),
                )
                existing = cur.fetchone()
                if existing:
                    skipped.append({"ticket_id": ticket["id"], "review_id": str(existing["id"])})
                    continue

                cur.execute(
                    """
                    UPDATE sync_reviews
                    SET review_status = 'stale', updated_at = now()
                    WHERE review_type = 'ticket_import'
                      AND target_type = 'ticket'
                      AND target_id = %s
                      AND review_status = 'pending'
                    """,
                    (ticket["id"],),
                )
                cur.execute(
                    """
                    INSERT INTO sync_reviews (
                      review_type, source_surface, target_surface, target_type, target_id,
                      base_version, current_version, proposed_changes, review_status
                    )
                    VALUES (
                      'ticket_import', 'vault_markdown', 'gm_dashboard_db', 'ticket', %(target_id)s,
                      '', %(current_version)s, %(proposed_changes)s, 'pending'
                    )
                    RETURNING id
                    """,
                    {
                        "target_id": ticket["id"],
                        "current_version": ticket["source_hash"],
                        "proposed_changes": psycopg2.extras.Json(
                            {
                                "action": "import_ticket",
                                "ticket": _json_safe(ticket),
                                "source_preserved": True,
                            }
                        ),
                    },
                )
                created.append({"ticket_id": ticket["id"], "review_id": str(cur.fetchone()["id"])})
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "review_type": "ticket_import",
        "found": len(tickets),
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "source_files_deleted": 0,
    }


@router.get("/tickets")
def list_tickets(stage: str | None = None, area: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = "SELECT * FROM tickets"
            params: list = []
            conditions: list[str] = []
            if stage:
                conditions.append("stage = %s")
                params.append(stage)
            if area:
                conditions.append("area = %s")
                params.append(area)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at ASC"
            cur.execute(query, params)
            return [_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
            return _row_to_dict(row)
    finally:
        conn.close()


@router.post("/tickets", status_code=201)
def create_ticket(payload: TicketCreate) -> dict:
    if payload.area not in VALID_AREAS:
        raise HTTPException(status_code=422, detail=f"Invalid area: {payload.area}")
    if payload.stage not in VALID_STAGES:
        raise HTTPException(status_code=422, detail=f"Invalid stage: {payload.stage}")
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {payload.status}")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Generate unique ID
            base_id = payload.id or _slugify(payload.title)
            candidate = base_id
            suffix = 2
            while True:
                cur.execute("SELECT 1 FROM tickets WHERE id = %s", (candidate,))
                if not cur.fetchone():
                    break
                candidate = f"{base_id}-{suffix}"
                suffix += 1

            cur.execute(
                """
                INSERT INTO tickets (
                  id, title, status, area, priority, stage, parent_id,
                  threads, depends_on, next_action, resume_note, source,
                  introduced, closed, resolution, review_after, lane,
                  classification, target_epic, source_path, source_hash,
                  source_mtime, review_status, body
                ) VALUES (
                  %(id)s, %(title)s, %(status)s, %(area)s, %(priority)s, %(stage)s, %(parent_id)s,
                  %(threads)s, %(depends_on)s, %(next_action)s, %(resume_note)s, %(source)s,
                  %(introduced)s, %(closed)s, %(resolution)s, %(review_after)s, %(lane)s,
                  %(classification)s, %(target_epic)s, %(source_path)s, %(source_hash)s,
                  %(source_mtime)s, %(review_status)s, %(body)s
                ) RETURNING *
                """,
                {
                    "id": candidate,
                    "title": payload.title,
                    "status": payload.status,
                    "area": payload.area,
                    "priority": payload.priority,
                    "stage": payload.stage,
                    "parent_id": payload.parent_id,
                    "threads": payload.threads,
                    "depends_on": payload.depends_on,
                    "next_action": payload.next_action,
                    "resume_note": payload.resume_note,
                    "source": payload.source,
                    "introduced": payload.introduced,
                    "closed": payload.closed,
                    "resolution": payload.resolution,
                    "review_after": payload.review_after,
                    "lane": payload.lane or payload.stage,
                    "classification": payload.classification,
                    "target_epic": payload.target_epic,
                    "source_path": payload.source_path,
                    "source_hash": payload.source_hash,
                    "source_mtime": payload.source_mtime,
                    "review_status": payload.review_status,
                    "body": payload.body,
                },
            )
            return _row_to_dict(cur.fetchone())
    finally:
        conn.close()


@router.put("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, payload: TicketUpdate) -> dict:
    if payload.area not in VALID_AREAS:
        raise HTTPException(status_code=422, detail=f"Invalid area: {payload.area}")
    if payload.stage not in VALID_STAGES:
        raise HTTPException(status_code=422, detail=f"Invalid stage: {payload.stage}")
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {payload.status}")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE tickets SET
                  title = %(title)s, status = %(status)s, area = %(area)s,
                  priority = %(priority)s, stage = %(stage)s, parent_id = %(parent_id)s,
                  threads = %(threads)s, depends_on = %(depends_on)s,
                  next_action = %(next_action)s, resume_note = %(resume_note)s,
                  source = %(source)s, introduced = %(introduced)s, closed = %(closed)s,
                  resolution = %(resolution)s, review_after = %(review_after)s,
                  lane = %(lane)s, classification = %(classification)s,
                  target_epic = %(target_epic)s, source_path = %(source_path)s,
                  source_hash = %(source_hash)s, source_mtime = %(source_mtime)s,
                  review_status = %(review_status)s,
                  body = %(body)s, updated_at = now()
                WHERE id = %(id)s
                RETURNING *
                """,
                {
                    "id": ticket_id,
                    "title": payload.title,
                    "status": payload.status,
                    "area": payload.area,
                    "priority": payload.priority,
                    "stage": payload.stage,
                    "parent_id": payload.parent_id,
                    "threads": payload.threads,
                    "depends_on": payload.depends_on,
                    "next_action": payload.next_action,
                    "resume_note": payload.resume_note,
                    "source": payload.source,
                    "introduced": payload.introduced,
                    "closed": payload.closed,
                    "resolution": payload.resolution,
                    "review_after": payload.review_after,
                    "lane": payload.lane or payload.stage,
                    "classification": payload.classification,
                    "target_epic": payload.target_epic,
                    "source_path": payload.source_path,
                    "source_hash": payload.source_hash,
                    "source_mtime": payload.source_mtime,
                    "review_status": payload.review_status,
                    "body": payload.body,
                },
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
            return _row_to_dict(row)
    finally:
        conn.close()


@router.patch("/tickets/{ticket_id}/stage")
def patch_ticket_stage(ticket_id: str, payload: TicketStagePatch) -> dict:
    if payload.stage not in VALID_STAGES:
        raise HTTPException(status_code=422, detail=f"Invalid stage: {payload.stage}. Must be one of {VALID_STAGES}")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE tickets SET stage = %s, lane = %s, updated_at = now() WHERE id = %s RETURNING *",
                (payload.stage, payload.stage, ticket_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
            return _row_to_dict(row)
    finally:
        conn.close()


@router.delete("/tickets/{ticket_id}")
def delete_ticket(ticket_id: str) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tickets WHERE id = %s RETURNING id", (ticket_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
            return {"deleted": True}
    finally:
        conn.close()
