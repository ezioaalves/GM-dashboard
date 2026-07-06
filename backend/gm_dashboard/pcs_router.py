from __future__ import annotations

from typing import Literal

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import services
from .db.get_db import get_connection
from .foundry_actors import fetch_actor_stats
from .relay_client import RelayError, load_relay_client
from .sheet_scan import sync_pc_sheets

router = APIRouter()


def _pc_row(row: dict) -> dict:
    out = dict(row)
    for key in ("foundry_last_synced_at", "created_at", "updated_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


def _get_pc_or_404(cur, slug: str) -> dict:
    cur.execute("SELECT * FROM pcs WHERE slug = %s", (slug,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"PC '{slug}' not found")
    return dict(row)


@router.get("/pcs")
def list_pcs(player: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if player is not None:
                cur.execute("SELECT * FROM pcs WHERE player = %s ORDER BY name", (player,))
            else:
                cur.execute("SELECT * FROM pcs ORDER BY name")
            return [_pc_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.get("/pcs/{slug}")
def get_pc(slug: str) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return _pc_row(_get_pc_or_404(cur, slug))
    finally:
        conn.close()


@router.post("/pcs/sync")
def sync_pcs() -> dict:
    vault_root = services.find_vault_root()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return sync_pc_sheets(vault_root, cur)
    finally:
        conn.close()


class PcRefreshRequest(BaseModel):
    env: Literal["test", "prod"] = "test"


@router.post("/pcs/{slug}/foundry/refresh")
def refresh_pc_from_foundry(slug: str, payload: PcRefreshRequest) -> dict:
    id_col = f"foundry_actor_id_{payload.env}"
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            pc = _get_pc_or_404(cur, slug)
            foundry_actor_id = pc.get(id_col)
            if not foundry_actor_id:
                raise HTTPException(status_code=404, detail=f"PC has no {id_col} to refresh from")

            try:
                client = load_relay_client(payload.env)
                fetched = fetch_actor_stats(client, foundry_actor_id)
            except RelayError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            cur.execute(
                """
                UPDATE pcs
                SET stats = %(stats)s,
                    foundry_last_synced_at = now(),
                    updated_at = now()
                WHERE slug = %(slug)s
                """,
                {"stats": psycopg2.extras.Json(fetched), "slug": slug},
            )
            return {"refreshed": True, "stats": fetched}
    finally:
        conn.close()
