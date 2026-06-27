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
                  introduced, closed, resolution, review_after, body
                ) VALUES (
                  %(id)s, %(title)s, %(status)s, %(area)s, %(priority)s, %(stage)s, %(parent_id)s,
                  %(threads)s, %(depends_on)s, %(next_action)s, %(resume_note)s, %(source)s,
                  %(introduced)s, %(closed)s, %(resolution)s, %(review_after)s, %(body)s
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
                    "body": payload.body,
                },
            )
            return _row_to_dict(cur.fetchone())
    finally:
        conn.close()


@router.put("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, payload: TicketUpdate) -> dict:
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
                "UPDATE tickets SET stage = %s, updated_at = now() WHERE id = %s RETURNING *",
                (payload.stage, ticket_id),
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
