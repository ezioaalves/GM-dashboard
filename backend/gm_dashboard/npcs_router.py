from __future__ import annotations

import psycopg2.extras
from fastapi import APIRouter, HTTPException

from . import services
from .db.get_db import get_connection
from .sheet_scan import sync_npc_sheets

router = APIRouter()


def _npc_row(row: dict) -> dict:
    out = dict(row)
    for key in ("foundry_last_synced_at", "created_at", "updated_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


def _get_npc_or_404(cur, slug: str) -> dict:
    cur.execute("SELECT * FROM npcs WHERE slug = %s", (slug,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"NPC '{slug}' not found")
    return dict(row)


@router.get("/npcs")
def list_npcs(affiliation: str | None = None, status: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: dict = {}
            if affiliation is not None:
                conditions.append("affiliation = %(affiliation)s")
                params["affiliation"] = affiliation
            if status is not None:
                conditions.append("status = %(status)s")
                params["status"] = status
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            cur.execute(f"SELECT * FROM npcs {where} ORDER BY name", params)
            return [_npc_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.get("/npcs/{slug}")
def get_npc(slug: str) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return _npc_row(_get_npc_or_404(cur, slug))
    finally:
        conn.close()


@router.post("/npcs/sync")
def sync_npcs() -> dict:
    vault_root = services.find_vault_root()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return sync_npc_sheets(vault_root, cur)
    finally:
        conn.close()
