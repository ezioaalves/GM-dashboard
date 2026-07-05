from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from .clock_engine import ConditionError, EngineError, fire_manual_tick, validate_condition
from .db.get_db import get_connection
from .system_enums import CLOCK_KINDS, CLOCK_LIFECYCLES, GRAPH_ENDPOINT_TYPES

router = APIRouter()


class ClockCreate(BaseModel):
    name: str
    kind: str = "progress"
    segments: int
    description: str = ""
    segment_labels: list[dict] = []
    visibility: str = "gm"

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name is required")
        return v.strip()

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        if v not in CLOCK_KINDS:
            raise ValueError(f"kind must be one of {sorted(CLOCK_KINDS)}")
        return v

    @field_validator("segments")
    @classmethod
    def segments_valid(cls, v: int) -> int:
        if not 1 <= v <= 32:
            raise ValueError("segments must be between 1 and 32")
        return v


class ClockUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    segments: int | None = None
    segment_labels: list[dict] | None = None
    visibility: str | None = None


class LifecycleUpdate(BaseModel):
    lifecycle: str
    resolution: str = ""

    @field_validator("lifecycle")
    @classmethod
    def lifecycle_valid(cls, v: str) -> str:
        if v not in CLOCK_LIFECYCLES:
            raise ValueError(f"lifecycle must be one of {sorted(CLOCK_LIFECYCLES)}")
        return v


class TickRequest(BaseModel):
    delta: int
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason is required")
        return v.strip()

    @field_validator("delta")
    @classmethod
    def delta_non_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("delta must be non-zero")
        return v


class LinkRequest(BaseModel):
    target_endpoint: str
    relationship_type: str = "tracks"

    @field_validator("target_endpoint")
    @classmethod
    def endpoint_valid(cls, v: str) -> str:
        prefix = v.split(":", 1)[0] if ":" in v else ""
        if prefix not in GRAPH_ENDPOINT_TYPES:
            raise ValueError(f"target_endpoint must start with one of {sorted(GRAPH_ENDPOINT_TYPES)}")
        return v


def _row_to_clock(row: dict) -> dict:
    out = dict(row)
    out["id"] = str(out["id"])
    for key in ("resolved_at", "last_mirrored_at", "created_at", "updated_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    out["mirror"] = {
        "state": out.pop("mirror_state"),
        "foundry_clock_id_test": out.pop("foundry_clock_id_test"),
        "foundry_clock_id_prod": out.pop("foundry_clock_id_prod"),
        "last_mirrored_at": out.pop("last_mirrored_at"),
    }
    return out


def _get_clock(cur, clock_id: str) -> dict:
    cur.execute("SELECT * FROM clocks WHERE id = %s", (clock_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Clock not found")
    return dict(row)


def _clock_links(cur, graph_endpoint_id: str) -> list[dict]:
    cur.execute(
        """
        SELECT id, target_type, target_id, relationship_type
        FROM lore_relationships
        WHERE source_type = 'clock' AND source_id = %s
        ORDER BY created_at
        """,
        (graph_endpoint_id,),
    )
    return [
        {"id": str(r["id"]), "target_type": r["target_type"],
         "target_id": r["target_id"], "relationship_type": r["relationship_type"]}
        for r in cur.fetchall()
    ]


@router.get("/clocks")
def list_clocks(
    lifecycle: str | None = None,
    kind: str | None = None,
    linked_to: str | None = None,
    mirrored: bool | None = None,
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions, params = [], []
            if lifecycle:
                conditions.append("lifecycle = %s")
                params.append(lifecycle)
            if kind:
                conditions.append("kind = %s")
                params.append(kind)
            if mirrored is True:
                conditions.append("mirror_state <> 'not_mirrored'")
            if mirrored is False:
                conditions.append("mirror_state = 'not_mirrored'")
            if linked_to:
                conditions.append(
                    """graph_endpoint_id IN (
                         SELECT source_id FROM lore_relationships
                         WHERE source_type = 'clock' AND target_id = %s
                       )"""
                )
                params.append(linked_to)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            cur.execute(f"SELECT * FROM clocks {where} ORDER BY created_at", params)
            return [_row_to_clock(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


@router.post("/clocks")
def create_clock(payload: ClockCreate) -> dict:
    filled = payload.segments if payload.kind == "countdown" else 0
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO clocks (name, description, kind, segments, filled,
                                    segment_labels, visibility)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (payload.name, payload.description, payload.kind, payload.segments,
                 filled, psycopg2.extras.Json(payload.segment_labels), payload.visibility),
            )
            row = dict(cur.fetchone())
            conn.commit()
            return _row_to_clock(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/clocks/{clock_id}")
def get_clock(clock_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            row = _get_clock(cur, str(clock_id))
            out = _row_to_clock(row)
            out["links"] = _clock_links(cur, row["graph_endpoint_id"])
            return out
    finally:
        conn.close()


@router.patch("/clocks/{clock_id}")
def update_clock(clock_id: UUID, payload: ClockUpdate) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="no fields to update")
    if "segments" in updates and not 1 <= updates["segments"] <= 32:
        raise HTTPException(status_code=422, detail="segments must be between 1 and 32")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            row = _get_clock(cur, str(clock_id))
            sets, params = [], {}
            for key, value in updates.items():
                if key == "segment_labels":
                    value = psycopg2.extras.Json(value)
                sets.append(f"{key} = %({key})s")
                params[key] = value
            if "segments" in updates:
                sets.append("filled = LEAST(filled, %(segments)s)")
            params["id"] = str(clock_id)
            cur.execute(
                f"UPDATE clocks SET {', '.join(sets)}, updated_at = now() "
                "WHERE id = %(id)s RETURNING *",
                params,
            )
            out = _row_to_clock(dict(cur.fetchone()))
            conn.commit()
            return out
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/clocks/{clock_id}/lifecycle")
def update_lifecycle(clock_id: UUID, payload: LifecycleUpdate) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _get_clock(cur, str(clock_id))
            if payload.lifecycle == "active":
                cur.execute(
                    """
                    UPDATE clocks SET lifecycle = 'active', resolution = '',
                                      resolved_at = NULL, updated_at = now()
                    WHERE id = %s RETURNING *
                    """,
                    (str(clock_id),),
                )
            else:
                cur.execute(
                    """
                    UPDATE clocks SET lifecycle = %s, resolution = %s,
                                      resolved_at = now(), updated_at = now()
                    WHERE id = %s RETURNING *
                    """,
                    (payload.lifecycle, payload.resolution, str(clock_id)),
                )
            out = _row_to_clock(dict(cur.fetchone()))
            conn.commit()
            return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/clocks/{clock_id}/ticks")
def tick_clock(clock_id: UUID, payload: TickRequest) -> dict:
    conn = get_connection()
    try:
        return fire_manual_tick(conn, str(clock_id), payload.delta, payload.reason)
    except EngineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/clocks/{clock_id}/ticks")
def clock_ticks(clock_id: UUID, limit: int = 100) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _get_clock(cur, str(clock_id))
            cur.execute(
                """
                SELECT t.*, r.name AS rule_name, r.title AS rule_title
                FROM clock_ticks t
                LEFT JOIN cascade_rules r ON r.id = t.rule_id
                WHERE t.clock_id = %s
                ORDER BY t.created_at DESC
                LIMIT %s
                """,
                (str(clock_id), max(1, min(limit, 500))),
            )
            out = []
            for row in cur.fetchall():
                item = dict(row)
                for key in ("id", "clock_id", "rule_id", "trigger_fire_id", "created_by"):
                    if item.get(key) is not None:
                        item[key] = str(item[key])
                item["created_at"] = item["created_at"].isoformat()
                out.append(item)
            return out
    finally:
        conn.close()


@router.post("/clocks/{clock_id}/links")
def add_clock_link(clock_id: UUID, payload: LinkRequest) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            row = _get_clock(cur, str(clock_id))
            target_type = payload.target_endpoint.split(":", 1)[0]
            cur.execute(
                """
                INSERT INTO lore_relationships (
                  source_type, source_id, target_type, target_id,
                  relationship_type, direction, provenance, review_status
                )
                VALUES ('clock', %s, %s, %s, %s, 'directed', 'manual', 'accepted')
                RETURNING id
                """,
                (row["graph_endpoint_id"], target_type, payload.target_endpoint,
                 payload.relationship_type),
            )
            rel_id = str(cur.fetchone()["id"])
            conn.commit()
            return {"id": rel_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/clocks/{clock_id}/links/{rel_id}")
def delete_clock_link(clock_id: UUID, rel_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            row = _get_clock(cur, str(clock_id))
            cur.execute(
                """
                DELETE FROM lore_relationships
                WHERE id = %s AND source_type = 'clock' AND source_id = %s
                RETURNING id
                """,
                (str(rel_id), row["graph_endpoint_id"]),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Link not found")
            conn.commit()
            return {"deleted": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
