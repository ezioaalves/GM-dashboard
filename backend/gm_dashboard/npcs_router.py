from __future__ import annotations

from typing import Literal

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import services
from .db.get_db import get_connection
from .foundry_actors import create_actor, fetch_actor_stats, render_npc_actor_payload
from .relay_client import RelayError, load_relay_client
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


class NpcForwardRequest(BaseModel):
    env: Literal["test", "prod"] = "test"


@router.post("/npcs/{slug}/foundry/push")
def push_npc_to_foundry(slug: str, payload: NpcForwardRequest) -> dict:
    id_col = f"foundry_actor_id_{payload.env}"
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            npc = _get_npc_or_404(cur, slug)
            if npc["foundry_sync_locked"]:
                raise HTTPException(status_code=409, detail="NPC has already been pushed once")
            if npc.get(id_col):
                raise HTTPException(status_code=409, detail=f"NPC already has a {id_col}")

            try:
                client = load_relay_client(payload.env)
                actor_payload = render_npc_actor_payload(npc)
                foundry_actor_id = create_actor(client, actor_payload)
            except RelayError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            cur.execute(
                f"""
                UPDATE npcs
                SET {id_col} = %(foundry_actor_id)s,
                    foundry_sync_locked = true,
                    foundry_last_synced_at = now(),
                    updated_at = now()
                WHERE slug = %(slug)s
                """,
                {"foundry_actor_id": foundry_actor_id, "slug": slug},
            )
            return {"pushed": True, "env": payload.env, "foundry_actor_id": foundry_actor_id}
    finally:
        conn.close()


@router.post("/npcs/{slug}/foundry/refresh")
def refresh_npc_from_foundry(slug: str, payload: NpcForwardRequest) -> dict:
    id_col = f"foundry_actor_id_{payload.env}"
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            npc = _get_npc_or_404(cur, slug)
            foundry_actor_id = npc.get(id_col)
            if not foundry_actor_id:
                raise HTTPException(status_code=404, detail=f"NPC has no {id_col} to refresh from")

            try:
                client = load_relay_client(payload.env)
                fetched = fetch_actor_stats(client, foundry_actor_id)
            except RelayError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            current_stats = npc.get("stats") or {}
            current_comparable = {
                "abilities": current_stats.get("abilities", {}),
                "naruto_stats": current_stats.get("naruto_stats", {}),
            }
            if fetched == current_comparable:
                return {"changed": False}

            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  base_version, current_version, proposed_changes, review_status
                )
                VALUES (
                  'npc_import', %(source_surface)s, 'postgres', 'npc', %(target_id)s,
                  '', '', %(proposed_changes)s, 'pending'
                )
                RETURNING id
                """,
                {
                    "source_surface": f"foundry_{payload.env}",
                    "target_id": str(npc["id"]),
                    "proposed_changes": psycopg2.extras.Json({"stats": fetched}),
                },
            )
            review_id = str(cur.fetchone()["id"])
            return {"changed": True, "review_id": review_id}
    finally:
        conn.close()
