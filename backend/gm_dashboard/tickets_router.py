from __future__ import annotations

import re
from datetime import date
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    body: str = ""


class TicketStagePatch(BaseModel):
    stage: str


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


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
        "body": row["body"] or "",
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
