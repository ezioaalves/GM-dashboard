from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from .clock_engine import (
    ConditionError,
    EngineError,
    fire_manual_tick,
    fire_rule,
    validate_condition,
)
from .db.get_db import engine_connection, get_connection
from .system_enums import (
    CASCADE_TRIGGER_KINDS,
    CLOCK_EVENTS,
    CLOCK_KINDS,
    CLOCK_LIFECYCLES,
    GRAPH_ENDPOINT_TYPES,
)
from . import clockworks_mirror
from .relay_client import RelayError

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


class MirrorRequest(BaseModel):
    env: Literal["test", "prod"] = "test"
    action: Literal["establish", "unmirror"] = "establish"


class AdoptDriftRequest(BaseModel):
    env: Literal["test", "prod"] = "test"
    reason: str
    foundry_value: int | None = None


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


@router.get("/clocks/mirror/drift")
def check_clock_mirror_drift(env: Literal["test", "prod"] = "test") -> dict:
    id_col = f"foundry_clock_id_{env}"
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT * FROM clocks
                WHERE {id_col} <> '' AND mirror_state <> 'not_mirrored'
                ORDER BY created_at
                """
            )
            rows = [dict(row) for row in cur.fetchall()]
            if not rows:
                return {"env": env, "checked": 0, "verdicts": []}
            try:
                client = clockworks_mirror.load_relay_client(env)
                verdicts = clockworks_mirror.check_drift(client, rows, env)
            except (RelayError, clockworks_mirror.MirrorError) as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            drift_ids = {v["clock_id"] for v in verdicts if v["kind"] == "value_drift"}
            missing_ids = {v["clock_id"] for v in verdicts if v["kind"] == "missing_mirror"}
            clean_ids = {str(row["id"]) for row in rows} - drift_ids - missing_ids
            if drift_ids:
                cur.execute(
                    "UPDATE clocks SET freshness_state = 'stale_mirror', updated_at = now() "
                    "WHERE id::text = ANY(%s)",
                    (list(drift_ids),),
                )
            if missing_ids:
                cur.execute(
                    "UPDATE clocks SET mirror_state = 'missing_mirror', updated_at = now() "
                    "WHERE id::text = ANY(%s)",
                    (list(missing_ids),),
                )
            if clean_ids:
                cur.execute(
                    "UPDATE clocks SET freshness_state = 'fresh', "
                    "mirror_state = CASE WHEN mirror_state = 'missing_mirror' THEN 'mirrored' ELSE mirror_state END, "
                    "updated_at = now() WHERE id::text = ANY(%s)",
                    (list(clean_ids),),
                )
            conn.commit()
            return {"env": env, "checked": len(rows), "verdicts": verdicts}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/clocks/{clock_id}/mirror/adopt")
def create_drift_adopt_review(clock_id: UUID, payload: AdoptDriftRequest) -> dict:
    if not payload.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required")
    id_col = f"foundry_clock_id_{payload.env}"
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            clock = _get_clock(cur, str(clock_id))
            if clock["freshness_state"] != "stale_mirror":
                raise HTTPException(status_code=409, detail="clock is not marked stale_mirror")
            foundry_value = payload.foundry_value
            if foundry_value is None:
                try:
                    client = clockworks_mirror.load_relay_client(payload.env)
                    verdicts = clockworks_mirror.check_drift(client, [clock], payload.env)
                except (RelayError, clockworks_mirror.MirrorError) as exc:
                    raise HTTPException(status_code=502, detail=str(exc)) from exc
                value_verdict = next(
                    (v for v in verdicts if v["clock_id"] == str(clock_id) and "value" in v.get("fields", {})),
                    None,
                )
                if value_verdict is None:
                    raise HTTPException(status_code=409, detail="no Foundry value drift to adopt")
                foundry_value = value_verdict["fields"]["value"]["foundry"]
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  base_version, current_version, proposed_changes, review_status
                )
                VALUES ('clock_drift_adopt', %(source_surface)s, 'postgres', 'clock', %(target_id)s,
                        %(base_version)s, %(current_version)s, %(proposed_changes)s, 'pending')
                RETURNING id, review_status
                """,
                {
                    "source_surface": f"foundry_{payload.env}",
                    "target_id": str(clock_id),
                    "base_version": str(clock["filled"]),
                    "current_version": str(foundry_value),
                    "proposed_changes": psycopg2.extras.Json({
                        "env": payload.env,
                        "foundry_value": foundry_value,
                        "reason": payload.reason.strip(),
                        "foundry_clock_id": clock[id_col],
                    }),
                },
            )
            row = dict(cur.fetchone())
            conn.commit()
            return {"id": str(row["id"]), "review_status": row["review_status"]}
    except HTTPException:
        conn.rollback()
        raise
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


@router.post("/clocks/{clock_id}/mirror")
def create_clock_mirror_review(clock_id: UUID, payload: MirrorRequest) -> dict:
    id_col = f"foundry_clock_id_{payload.env}"
    target_surface = f"foundry_{payload.env}"
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            clock = _get_clock(cur, str(clock_id))
            current_foundry_id = clock[id_col]
            if payload.action == "establish" and current_foundry_id:
                raise HTTPException(status_code=409, detail=f"clock is already mirrored to {payload.env}")
            if payload.action == "unmirror" and not current_foundry_id:
                raise HTTPException(status_code=409, detail=f"clock is not mirrored to {payload.env}")
            cur.execute(
                """
                SELECT id FROM sync_reviews
                WHERE review_type = 'clock_mirror'
                  AND target_type = 'clock'
                  AND target_id = %s
                  AND target_surface = %s
                  AND review_status = 'pending'
                """,
                (str(clock_id), target_surface),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="pending clock mirror review already exists")
            if payload.action == "unmirror":
                proposed = {
                    "action": "unmirror",
                    "env": payload.env,
                    "foundry_clock_id": current_foundry_id,
                }
            else:
                foundry_id = current_foundry_id or clockworks_mirror.new_foundry_id()
                proposed = {
                    "action": "establish",
                    "env": payload.env,
                    "entry": clockworks_mirror.render_clockworks_entry(clock, foundry_id),
                }
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  base_version, current_version, proposed_changes, review_status
                )
                VALUES ('clock_mirror', 'postgres', %(target_surface)s, 'clock', %(target_id)s,
                        %(base_version)s, %(current_version)s, %(proposed_changes)s, 'pending')
                RETURNING id, review_status
                """,
                {
                    "target_surface": target_surface,
                    "target_id": str(clock_id),
                    "base_version": "",
                    "current_version": str(clock["updated_at"]),
                    "proposed_changes": psycopg2.extras.Json(proposed),
                },
            )
            row = dict(cur.fetchone())
            conn.commit()
            return {"id": str(row["id"]), "review_status": row["review_status"]}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
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
    # Engine fires need a real transaction (FOR UPDATE lock held across the
    # whole fire; atomic rollback on failure) — not autocommit get_connection().
    with engine_connection() as conn:
        try:
            return fire_manual_tick(conn, str(clock_id), payload.delta, payload.reason)
        except EngineError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


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


def _check_trigger_kind(v: str) -> str:
    if v not in CASCADE_TRIGGER_KINDS:
        raise ValueError(f"trigger_kind must be one of {sorted(CASCADE_TRIGGER_KINDS)}")
    return v


def _check_effects(v: list[dict]) -> list[dict]:
    if not v:
        raise ValueError("at least one effect is required")
    for effect in v:
        if not effect.get("clock_id"):
            raise ValueError("every effect needs a clock_id")
        delta = effect.get("delta")
        if not isinstance(delta, int) or delta == 0:
            raise ValueError("every effect needs a non-zero integer delta")
        if not isinstance(effect.get("reason_template", ""), str):
            raise ValueError("effect reason_template must be a string")
    return v


class CascadeRuleCreate(BaseModel):
    name: str
    title: str = ""
    description: str = ""
    trigger_kind: str = "manual"
    trigger_clock_id: str | None = None
    trigger_event: str | None = None
    condition: dict = {}
    effects: list[dict]
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def name_slug(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name is required")
        return v.strip()

    @field_validator("trigger_kind")
    @classmethod
    def trigger_kind_valid(cls, v: str) -> str:
        return _check_trigger_kind(v)

    @field_validator("effects")
    @classmethod
    def effects_shape(cls, v: list[dict]) -> list[dict]:
        return _check_effects(v)


class CascadeRuleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    trigger_kind: str | None = None
    trigger_clock_id: str | None = None
    trigger_event: str | None = None
    condition: dict | None = None
    effects: list[dict] | None = None
    enabled: bool | None = None

    @field_validator("trigger_kind")
    @classmethod
    def trigger_kind_valid(cls, v: str | None) -> str | None:
        return v if v is None else _check_trigger_kind(v)

    @field_validator("effects")
    @classmethod
    def effects_shape(cls, v: list[dict] | None) -> list[dict] | None:
        return v if v is None else _check_effects(v)


class FireRequest(BaseModel):
    dry_run: bool = False
    trigger_note: str = ""


def _validate_rule_semantics(cur, data: dict) -> None:
    if data.get("trigger_kind") == "clock_event":
        if not data.get("trigger_clock_id") or data.get("trigger_event") not in CLOCK_EVENTS:
            raise HTTPException(
                status_code=422,
                detail="clock_event rules need trigger_clock_id and a valid trigger_event",
            )
    try:
        validate_condition(data.get("condition") or {})
    except ConditionError as exc:
        raise HTTPException(status_code=422, detail=f"condition: {exc}") from exc
    clock_ids = {str(e["clock_id"]) for e in data.get("effects") or []}
    if data.get("trigger_clock_id"):
        clock_ids.add(str(data["trigger_clock_id"]))
    if clock_ids:
        cur.execute("SELECT id::text FROM clocks WHERE id::text = ANY(%s)", (list(clock_ids),))
        found = {r["id"] for r in cur.fetchall()}
        missing = clock_ids - found
        if missing:
            raise HTTPException(status_code=422, detail=f"unknown clock ids: {sorted(missing)}")


def _rule_out(row: dict) -> dict:
    out = dict(row)
    for key in ("id", "trigger_clock_id"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    for key in ("created_at", "updated_at"):
        out[key] = out[key].isoformat()
    return out


@router.get("/cascades")
def list_cascades() -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM cascade_rules ORDER BY name")
            return [_rule_out(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


@router.post("/cascades")
def create_cascade(payload: CascadeRuleCreate) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _validate_rule_semantics(cur, payload.model_dump())
            cur.execute(
                """
                INSERT INTO cascade_rules
                  (name, title, description, trigger_kind, trigger_clock_id,
                   trigger_event, condition, effects, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (payload.name, payload.title, payload.description, payload.trigger_kind,
                 payload.trigger_clock_id, payload.trigger_event,
                 psycopg2.extras.Json(payload.condition),
                 psycopg2.extras.Json(payload.effects), payload.enabled),
            )
            out = _rule_out(dict(cur.fetchone()))
            conn.commit()
            return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/cascades/{rule_id}")
def get_cascade(rule_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM cascade_rules WHERE id = %s", (str(rule_id),))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Cascade rule not found")
            return _rule_out(dict(row))
    finally:
        conn.close()


@router.patch("/cascades/{rule_id}")
def update_cascade(rule_id: UUID, payload: CascadeRuleUpdate) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="no fields to update")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM cascade_rules WHERE id = %s", (str(rule_id),))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Cascade rule not found")
            merged = {**dict(row), **updates}
            _validate_rule_semantics(cur, merged)
            sets, params = [], {}
            for key, value in updates.items():
                if key in ("condition", "effects"):
                    value = psycopg2.extras.Json(value)
                sets.append(f"{key} = %({key})s")
                params[key] = value
            params["id"] = str(rule_id)
            cur.execute(
                f"UPDATE cascade_rules SET {', '.join(sets)}, updated_at = now() "
                "WHERE id = %(id)s RETURNING *",
                params,
            )
            out = _rule_out(dict(cur.fetchone()))
            conn.commit()
            return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/cascades/{rule_id}")
def delete_cascade(rule_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("DELETE FROM cascade_rules WHERE id = %s RETURNING id", (str(rule_id),))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Cascade rule not found")
            conn.commit()
            return {"deleted": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/cascades/{rule_id}/fire")
def fire_cascade(rule_id: UUID, payload: FireRequest) -> dict:
    # Engine fires need a real transaction (atomic cascade rollback + FOR UPDATE
    # locks) — never the autocommit get_connection(). Same helper as the tick route.
    with engine_connection() as conn:
        try:
            return fire_rule(conn, str(rule_id), trigger_note=payload.trigger_note,
                             dry_run=payload.dry_run)
        except EngineError as exc:
            status = 422 if "manual" in str(exc) or "condition" in str(exc) else 409
            raise HTTPException(status_code=status, detail=str(exc)) from exc
