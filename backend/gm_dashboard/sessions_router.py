from __future__ import annotations

import psycopg2.errors
import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .db.get_db import get_connection

router = APIRouter()


class SessionCreate(BaseModel):
    number: int
    name: str = ""


def _row_to_dict(row: dict) -> dict:
    return {"id": row["id"], "number": row["number"], "name": row["name"]}


@router.get("/sessions")
def list_sessions() -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, number, name FROM sessions ORDER BY number DESC")
            return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@router.post("/sessions", status_code=201)
def create_session(payload: SessionCreate) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                cur.execute(
                    "INSERT INTO sessions (number, name) VALUES (%s, %s) RETURNING id, number, name",
                    (payload.number, payload.name),
                )
            except psycopg2.errors.UniqueViolation:
                raise HTTPException(status_code=409, detail=f"Session {payload.number} already exists")
            return _row_to_dict(cur.fetchone())
    finally:
        conn.close()
