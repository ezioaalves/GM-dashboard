from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .db.get_db import get_connection
from .system_enums import ASSET_STATUSES, DECISION_REVIEW_STATUSES

router = APIRouter()


class SyncReviewDecision(BaseModel):
    review_status: str
    decision: dict[str, Any] = {}


class SyncReviewApplyRequest(BaseModel):
    confirmation: bool = False
    confirm: bool = False
    selected_change_ids: list[str] = []
    target_surface: str | None = None

    def is_confirmed(self) -> bool:
        return self.confirmation is True or self.confirm is True

    def audit_payload(self, review: dict) -> dict[str, Any]:
        target_surface = self.target_surface or review["target_surface"]
        return {
            "review_id": review["id"],
            "review_type": review["review_type"],
            "target_type": review["target_type"],
            "target_id": review["target_id"],
            "selected_change_ids": self.selected_change_ids,
            "target_surface": target_surface,
        }


def _json(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return value


def _review(cur, review_id: str) -> dict:
    cur.execute("SELECT * FROM sync_reviews WHERE id = %s", (review_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sync review not found")
    return _json(dict(row))


def _sync_job(cur, job_id: str) -> dict:
    cur.execute("SELECT * FROM sync_jobs WHERE id = %s", (job_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return _json(dict(row))


def _completed_apply_result(cur, review: dict) -> dict | None:
    if not review.get("applied_at"):
        return None
    job_id = review.get("sync_job_id")
    if not job_id:
        raise HTTPException(status_code=409, detail="review was applied but has no sync job")
    job = _sync_job(cur, job_id)
    result = job.get("result_payload") or job.get("result") or {}
    if not isinstance(result, dict):
        result = {"result": result}
    return {**result, "already_applied": True, "sync_job_id": job["id"]}


def _insert_apply_job(cur, review: dict, audit_payload: dict[str, Any]) -> str:
    cur.execute(
        """
        INSERT INTO sync_jobs (
          target, direction, status, diff, job_type,
          source_surface, target_surface, review_id, payload, input_payload,
          started_at, updated_at
        )
        VALUES (
          %(target)s, %(direction)s, 'running', '', 'apply_review',
          %(source_surface)s, %(target_surface)s, %(review_id)s, %(payload)s,
          %(payload)s, now(), now()
        )
        RETURNING id
        """,
        {
            "target": f"{review['target_type']}:{review['target_id']}",
            "direction": f"{review['source_surface']}_to_{review['target_surface']}",
            "source_surface": review["source_surface"],
            "target_surface": review["target_surface"],
            "review_id": review["id"],
            "payload": psycopg2.extras.Json(audit_payload),
        },
    )
    job_id = str(cur.fetchone()["id"])
    cur.execute(
        "UPDATE sync_reviews SET sync_job_id = %s, updated_at = now() WHERE id = %s",
        (job_id, review["id"]),
    )
    return job_id


def _finish_apply_job(cur, job_id: str, result: dict[str, Any]) -> dict:
    result_with_job = {**result, "sync_job_id": job_id}
    cur.execute(
        """
        UPDATE sync_jobs
        SET status = 'succeeded',
            result = %(result)s,
            result_payload = %(result)s,
            finished_at = now(),
            updated_at = now()
        WHERE id = %(id)s
        """,
        {"id": job_id, "result": psycopg2.extras.Json(result_with_job)},
    )
    return result_with_job


def _apply_ticket_import(cur, review: dict) -> dict:
    payload = review["proposed_changes"] or {}
    ticket = payload.get("ticket") or {}
    if not ticket.get("id"):
        raise HTTPException(status_code=409, detail="ticket_import review has no ticket payload")

    cur.execute(
        """
        INSERT INTO tickets (
          id, title, status, area, priority, stage, parent_id,
          threads, depends_on, next_action, resume_note, source,
          introduced, closed, resolution, review_after, lane,
          classification, target_epic, source_path, source_hash,
          source_mtime, review_status, body
        )
        VALUES (
          %(id)s, %(title)s, %(status)s, %(area)s, %(priority)s, %(stage)s, %(parent_id)s,
          %(threads)s, %(depends_on)s, %(next_action)s, %(resume_note)s, %(source)s,
          %(introduced)s, %(closed)s, %(resolution)s, %(review_after)s, %(lane)s,
          %(classification)s, %(target_epic)s, %(source_path)s, %(source_hash)s,
          %(source_mtime)s, 'accepted', %(body)s
        )
        ON CONFLICT (id) DO UPDATE SET
          title = EXCLUDED.title,
          status = EXCLUDED.status,
          area = EXCLUDED.area,
          priority = EXCLUDED.priority,
          stage = EXCLUDED.stage,
          parent_id = EXCLUDED.parent_id,
          threads = EXCLUDED.threads,
          depends_on = EXCLUDED.depends_on,
          next_action = EXCLUDED.next_action,
          resume_note = EXCLUDED.resume_note,
          source = EXCLUDED.source,
          introduced = EXCLUDED.introduced,
          closed = EXCLUDED.closed,
          resolution = EXCLUDED.resolution,
          review_after = EXCLUDED.review_after,
          lane = EXCLUDED.lane,
          classification = EXCLUDED.classification,
          target_epic = EXCLUDED.target_epic,
          source_path = EXCLUDED.source_path,
          source_hash = EXCLUDED.source_hash,
          source_mtime = EXCLUDED.source_mtime,
          review_status = 'accepted',
          body = EXCLUDED.body,
          updated_at = now()
        RETURNING id
        """,
        ticket,
    )
    ticket_id = cur.fetchone()["id"]
    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted',
            applied_at = now(),
            updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {"applied": True, "ticket_id": ticket_id, "source_files_deleted": 0}


def _apply_thread_import(cur, review: dict) -> dict:
    payload = review["proposed_changes"] or {}
    thread = payload.get("thread") or {}
    if not thread.get("id"):
        raise HTTPException(status_code=409, detail="thread_import review has no thread payload")

    cur.execute(
        """
        INSERT INTO threads (
          id, title, status, priority, arc, theme, pressure, stakes, next_move,
          clock_label, clock_value, clock_max, unresolved_questions, last_touched_at,
          visibility, freshness_state, review_status, factions, sessions, vault_path, body
        )
        VALUES (
          %(id)s, %(title)s, %(status)s, %(priority)s, %(arc)s, %(theme)s,
          %(pressure)s, %(stakes)s, %(next_move)s, %(clock_label)s, %(clock_value)s,
          %(clock_max)s, %(unresolved_questions)s, %(last_touched_at)s,
          %(visibility)s, %(freshness_state)s, 'accepted', %(factions)s,
          %(sessions)s, %(vault_path)s, %(body)s
        )
        ON CONFLICT (id) DO UPDATE SET
          title = EXCLUDED.title,
          status = EXCLUDED.status,
          priority = EXCLUDED.priority,
          arc = EXCLUDED.arc,
          theme = EXCLUDED.theme,
          pressure = EXCLUDED.pressure,
          stakes = EXCLUDED.stakes,
          next_move = EXCLUDED.next_move,
          clock_label = EXCLUDED.clock_label,
          clock_value = EXCLUDED.clock_value,
          clock_max = EXCLUDED.clock_max,
          unresolved_questions = EXCLUDED.unresolved_questions,
          last_touched_at = EXCLUDED.last_touched_at,
          visibility = EXCLUDED.visibility,
          freshness_state = EXCLUDED.freshness_state,
          review_status = 'accepted',
          factions = EXCLUDED.factions,
          sessions = EXCLUDED.sessions,
          vault_path = EXCLUDED.vault_path,
          body = EXCLUDED.body,
          updated_at = now()
        RETURNING id
        """,
        thread,
    )
    thread_id = cur.fetchone()["id"]
    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted',
            applied_at = now(),
            updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {"applied": True, "thread_id": thread_id, "source_files_deleted": 0}


def _apply_relationship_change(cur, review: dict) -> dict:
    payload = review["proposed_changes"] or {}
    relationships = payload.get("relationships") or []
    if not relationships:
        raise HTTPException(status_code=409, detail="relationship_change review has no relationships")

    relationship_ids: list[str] = []
    for relationship in relationships:
        cur.execute(
            """
            INSERT INTO lore_relationships (
              source_type, source_id, target_type, target_id, unresolved_target,
              relationship_type, direction, provenance, confidence, context,
              visibility, freshness_state, review_status, metadata
            )
            VALUES (
              %(source_type)s, %(source_id)s, %(target_type)s, %(target_id)s,
              %(unresolved_target)s, %(relationship_type)s, %(direction)s,
              %(provenance)s, %(confidence)s, %(context)s, %(visibility)s,
              %(freshness_state)s, 'accepted', %(metadata)s
            )
            RETURNING id
            """,
            {
                "source_type": relationship["source_type"],
                "source_id": relationship["source_id"],
                "target_type": relationship["target_type"],
                "target_id": relationship.get("target_id", ""),
                "unresolved_target": relationship.get("unresolved_target", ""),
                "relationship_type": relationship["relationship_type"],
                "direction": relationship.get("direction", "directed"),
                "provenance": relationship.get("provenance", "manual"),
                "confidence": relationship.get("confidence"),
                "context": relationship.get("context", ""),
                "visibility": relationship.get("visibility", "gm"),
                "freshness_state": relationship.get("freshness_state", "unknown"),
                "metadata": psycopg2.extras.Json(relationship.get("metadata") or {}),
            },
        )
        relationship_ids.append(str(cur.fetchone()["id"]))

    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted',
            applied_at = now(),
            updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {"applied": True, "relationship_ids": relationship_ids}


def _apply_vault_import(cur, review: dict) -> dict:
    payload = review["proposed_changes"] or {}
    entity_payload = payload.get("entity") or {}
    if not entity_payload.get("slug"):
        raise HTTPException(status_code=409, detail="vault_import review has no entity payload")

    source_paths = payload.get("source_paths") or []
    source_path = source_paths[0] if source_paths else ""

    cur.execute(
        """
        INSERT INTO lore_entities (slug, title, entity_type, source_path, source_hash, review_status)
        VALUES (%(slug)s, %(title)s, %(entity_type)s, %(source_path)s, %(source_hash)s, 'accepted')
        ON CONFLICT (entity_type, slug) DO UPDATE SET
          title = EXCLUDED.title,
          entity_type = EXCLUDED.entity_type,
          source_path = EXCLUDED.source_path,
          source_hash = EXCLUDED.source_hash,
          review_status = 'accepted',
          updated_at = now()
        RETURNING id, graph_endpoint_id
        """,
        {
            "slug": entity_payload["slug"],
            "title": entity_payload.get("title", entity_payload["slug"]),
            "entity_type": entity_payload.get("entity_type", "article"),
            "source_path": source_path,
            "source_hash": review["current_version"],
        },
    )
    entity_row = cur.fetchone()
    entity_id = str(entity_row["id"])
    graph_endpoint_id = entity_row["graph_endpoint_id"]

    cur.execute(
        """
        INSERT INTO lore_sources (source_surface, source_path, source_hash, review_status)
        VALUES ('vault', %(source_path)s, %(source_hash)s, 'accepted')
        ON CONFLICT (source_surface, source_path) DO UPDATE SET
          source_hash = EXCLUDED.source_hash,
          review_status = 'accepted',
          updated_at = now()
        RETURNING id
        """,
        {"source_path": source_path, "source_hash": review["current_version"]},
    )
    source_id = str(cur.fetchone()["id"])
    cur.execute(
        "UPDATE lore_entities SET primary_source_id = %s WHERE id = %s",
        (source_id, entity_id),
    )

    proposed_sections = payload.get("sections") or []
    proposed_paths = {tuple(s["heading_path"]) for s in proposed_sections}
    cur.execute("SELECT id, heading_path FROM lore_sections WHERE entity_id = %s", (entity_id,))
    for row in cur.fetchall():
        if tuple(row["heading_path"]) not in proposed_paths:
            cur.execute("DELETE FROM lore_sections WHERE id = %s", (row["id"],))

    for section in proposed_sections:
        params = {
            "source_id": source_id,
            "entity_id": entity_id,
            "heading": section["heading"],
            "body": section["body"],
            "section_order": section["section_order"],
            "heading_path": section["heading_path"],
            "start_line": section["start_line"],
            "end_line": section["end_line"],
        }
        cur.execute(
            """
            INSERT INTO lore_sections (
              source_id, entity_id, heading, body, section_order, heading_path,
              start_line, end_line, review_status
            )
            SELECT %(source_id)s, %(entity_id)s, %(heading)s, %(body)s, %(section_order)s,
                   %(heading_path)s, %(start_line)s, %(end_line)s, 'accepted'
            WHERE NOT EXISTS (
              SELECT 1 FROM lore_sections
              WHERE entity_id = %(entity_id)s AND heading_path = %(heading_path)s
            )
            """,
            params,
        )
        cur.execute(
            """
            UPDATE lore_sections
            SET body = %(body)s, section_order = %(section_order)s,
                start_line = %(start_line)s, end_line = %(end_line)s, updated_at = now()
            WHERE entity_id = %(entity_id)s AND heading_path = %(heading_path)s
            """,
            params,
        )

    relationship_ids: list[str] = []
    for relationship in payload.get("relationships") or []:
        source_id_value = relationship.get("source_id") or graph_endpoint_id
        target_id_value = relationship.get("target_id", "")
        unresolved = relationship.get("unresolved_target", "")
        cur.execute(
            """
            SELECT id FROM lore_relationships
            WHERE source_type = 'entity' AND source_id = %(source_id)s
              AND target_type = %(target_type)s
              AND target_id = %(target_id)s
              AND relationship_type = %(relationship_type)s
            """,
            {
                "source_id": source_id_value,
                "target_type": relationship["target_type"],
                "target_id": target_id_value,
                "relationship_type": relationship["relationship_type"],
            },
        )
        if cur.fetchone():
            continue
        cur.execute(
            """
            INSERT INTO lore_relationships (
              source_type, source_id, target_type, target_id, unresolved_target,
              relationship_type, provenance, review_status
            )
            VALUES ('entity', %(source_id)s, %(target_type)s, %(target_id)s, %(unresolved_target)s,
                    %(relationship_type)s, %(provenance)s, 'accepted')
            RETURNING id
            """,
            {
                "source_id": source_id_value,
                "target_type": relationship["target_type"],
                "target_id": target_id_value,
                "unresolved_target": unresolved,
                "relationship_type": relationship["relationship_type"],
                "provenance": relationship.get("provenance", "manual"),
            },
        )
        relationship_ids.append(str(cur.fetchone()["id"]))

    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted', applied_at = now(), updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {
        "applied": True,
        "entity_id": entity_id,
        "source_id": source_id,
        "relationship_ids": relationship_ids,
    }


def _apply_asset_import(cur, review: dict) -> dict:
    payload = review["proposed_changes"] or {}
    source_path = payload.get("source_path", "")
    if not source_path:
        raise HTTPException(status_code=409, detail="asset_import review has no asset payload")

    status = payload.get("status", "current")
    if status not in ASSET_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(ASSET_STATUSES)}"
        )

    duplicate_of = payload.get("duplicate_of")
    freshness_state = "conflict" if duplicate_of else "fresh"

    cur.execute(
        """
        INSERT INTO lore_assets (
          source_path, source_hash, asset_type, status, title, width, height,
          review_status, freshness_state, last_checked_at
        )
        VALUES (
          %(source_path)s, %(source_hash)s, %(asset_type)s, %(status)s, %(title)s,
          %(width)s, %(height)s, 'accepted', %(freshness_state)s, now()
        )
        ON CONFLICT (source_path) DO UPDATE SET
          source_hash = EXCLUDED.source_hash,
          asset_type = EXCLUDED.asset_type,
          status = EXCLUDED.status,
          title = EXCLUDED.title,
          width = EXCLUDED.width,
          height = EXCLUDED.height,
          review_status = 'accepted',
          freshness_state = EXCLUDED.freshness_state,
          last_checked_at = now(),
          updated_at = now()
        RETURNING id
        """,
        {
            "source_path": source_path,
            "source_hash": payload.get("source_hash", review["current_version"]),
            "asset_type": payload.get("asset_type", "image"),
            "status": status,
            "title": payload.get("title", ""),
            "width": payload.get("width"),
            "height": payload.get("height"),
            "freshness_state": freshness_state,
        },
    )
    asset_id = str(cur.fetchone()["id"])

    if duplicate_of:
        cur.execute(
            """
            UPDATE lore_assets
            SET freshness_state = 'conflict', updated_at = now()
            WHERE source_path = %s
            """,
            (duplicate_of,),
        )

    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted', applied_at = now(), updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {"applied": True, "asset_id": asset_id, "conflict_with": duplicate_of}


def _apply_npc_import(cur, review: dict) -> dict:
    payload = review["proposed_changes"] or {}
    stats = payload.get("stats")
    if stats is None:
        raise HTTPException(status_code=409, detail="npc_import review has no stats payload")

    cur.execute(
        """
        UPDATE npcs
        SET stats = COALESCE(stats, '{}'::jsonb) || %(stats)s::jsonb,
            foundry_last_synced_at = now(),
            updated_at = now()
        WHERE id = %(id)s
        RETURNING id
        """,
        {"stats": psycopg2.extras.Json(stats), "id": int(review["target_id"])},
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=409, detail=f"npc {review['target_id']} no longer exists")

    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted', applied_at = now(), updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {"applied": True, "npc_id": str(row["id"])}


def _apply_clock_mirror(cur, review: dict) -> dict:
    from . import clockworks_mirror

    changes = review["proposed_changes"] or {}
    env = changes["env"]
    id_col = f"foundry_clock_id_{env}"
    other_env = "prod" if env == "test" else "test"
    target_id = str(review["target_id"])
    cur.execute("SELECT * FROM clocks WHERE id::text = %s FOR UPDATE", (target_id,))
    clock = cur.fetchone()
    if clock is None:
        raise HTTPException(status_code=409, detail=f"clock {target_id} no longer exists")

    client = clockworks_mirror.load_relay_client(env)
    if changes["action"] == "unmirror":
        foundry_id = changes["foundry_clock_id"]
        clockworks_mirror.remove_entry(client, foundry_id)
        cur.execute(
            f"""
            UPDATE clocks
            SET {id_col} = '',
                mirror_state = CASE WHEN foundry_clock_id_{other_env} = ''
                                    THEN 'not_mirrored' ELSE 'mirrored' END,
                updated_at = now()
            WHERE id = %s
            """,
            (clock["id"],),
        )
        cur.execute(
            """
            UPDATE sync_reviews
            SET review_status = 'accepted', applied_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (review["id"],),
        )
        return {"applied": True, "action": "unmirror", "env": env, "removed": foundry_id}

    entry = dict(changes["entry"])
    entry.update(clockworks_mirror.render_clockworks_entry(clock, entry["id"]))
    clockworks_mirror.push_entry(client, entry)
    cur.execute(
        f"""
        UPDATE clocks
        SET {id_col} = %s,
            mirror_state = 'mirrored',
            last_mirrored_at = now(),
            freshness_state = 'fresh',
            updated_at = now()
        WHERE id = %s
        """,
        (entry["id"], clock["id"]),
    )
    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted', applied_at = now(), updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {
        "applied": True,
        "action": "establish",
        "env": env,
        "foundry_clock_id": entry["id"],
        "entry": entry,
    }


def _apply_clock_drift_adopt(cur, review: dict) -> dict:
    from .clock_engine import fire_manual_tick

    changes = review["proposed_changes"] or {}
    cur.execute("SELECT * FROM clocks WHERE id::text = %s FOR UPDATE", (str(review["target_id"]),))
    clock = cur.fetchone()
    if clock is None:
        raise HTTPException(status_code=409, detail=f"clock {review['target_id']} no longer exists")
    foundry_value = int(changes["foundry_value"])
    delta = foundry_value - clock["filled"]
    if delta == 0:
        cur.execute(
            "UPDATE clocks SET freshness_state = 'fresh', updated_at = now() WHERE id = %s",
            (clock["id"],),
        )
        fire_result = {"trigger_fire_id": "", "dry_run": False, "applied": []}
    else:
        fire_result = fire_manual_tick(
            cur.connection,
            str(clock["id"]),
            delta,
            reason=changes.get("reason") or f"Adopted Foundry {changes['env']} value {foundry_value}",
            dry_run=False,
            caused_by="drift_adopt",
        )
        cur.execute(
            "UPDATE clocks SET freshness_state = 'fresh', updated_at = now() WHERE id = %s",
            (clock["id"],),
        )
    cur.execute(
        """
        UPDATE sync_reviews
        SET review_status = 'accepted', applied_at = now(), updated_at = now()
        WHERE id = %s
        """,
        (review["id"],),
    )
    return {"applied": True, "action": "drift_adopt", "delta": delta, "fire_result": fire_result}


@router.get("/sync/reviews")
def list_sync_reviews(
    review_status: str | None = None,
    review_type: str | None = None,
    target_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: list[Any] = []
            if review_status:
                conditions.append("review_status = %s")
                params.append(review_status)
            if review_type:
                conditions.append("review_type = %s")
                params.append(review_type)
            if target_type:
                conditions.append("target_type = %s")
                params.append(target_type)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(max(1, min(limit, 500)))
            cur.execute(
                f"""
                SELECT id, review_type, source_surface, target_surface, target_type, target_id,
                       base_version, current_version, conflict_flags, review_status,
                       created_at, updated_at, decided_at, applied_at
                FROM sync_reviews
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            return [_json(dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()


@router.get("/sync/reviews/grouped")
def list_grouped_sync_reviews() -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, review_type, source_surface, target_surface, target_type, target_id,
                       base_version, current_version, conflict_flags, review_status,
                       created_at, updated_at, decided_at, applied_at
                FROM sync_reviews
                WHERE review_status IN ('pending', 'conflict', 'stale')
                ORDER BY target_type ASC, created_at DESC
                """
            )
            rows = [_json(dict(row)) for row in cur.fetchall()]
            groups: dict[str, list[dict]] = {}
            for row in rows:
                groups.setdefault(row["target_type"], []).append(row)
            return {
                "groups": [
                    {"target_type": target_type, "count": len(reviews), "reviews": reviews}
                    for target_type, reviews in sorted(groups.items())
                ]
            }
    finally:
        conn.close()


@router.get("/sync/reviews/{review_id}")
def get_sync_review(review_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return _review(cur, str(review_id))
    finally:
        conn.close()


@router.get("/sync/jobs/{job_id}")
def get_sync_job(job_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return _sync_job(cur, str(job_id))
    finally:
        conn.close()


@router.get("/sync/freshness")
def sync_freshness() -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  (SELECT count(*) FROM sync_reviews WHERE review_status = 'pending') AS pending_reviews,
                  (SELECT count(*) FROM sync_reviews WHERE review_status = 'conflict') AS conflict_reviews,
                  (SELECT count(*) FROM sync_reviews WHERE review_status = 'stale') AS stale_reviews,
                  (SELECT count(*) FROM sync_jobs WHERE status = 'failed') AS failed_jobs,
                  (SELECT count(*) FROM sync_jobs WHERE status = 'blocked') AS blocked_jobs,
                  (
                    SELECT count(*) FROM lore_sources
                    WHERE freshness_state <> 'fresh'
                  ) +
                  (
                    SELECT count(*) FROM lore_entities
                    WHERE freshness_state <> 'fresh'
                  ) +
                  (
                    SELECT count(*) FROM lore_sections
                    WHERE freshness_state <> 'fresh'
                  ) +
                  (
                    SELECT count(*) FROM lore_relationships
                    WHERE freshness_state <> 'fresh'
                  ) +
                  (
                    SELECT count(*) FROM lore_assets
                    WHERE freshness_state <> 'fresh'
                       OR mirror_state IN ('stale_mirror', 'missing_source', 'missing_mirror', 'conflict', 'failed')
                  ) +
                  (
                    SELECT count(*) FROM threads
                    WHERE freshness_state <> 'fresh'
                  ) +
                  (
                    SELECT count(*) FROM sessions
                    WHERE freshness_state <> 'fresh'
                  ) +
                  (
                    SELECT count(*) FROM scenes
                    WHERE freshness_state <> 'fresh'
                  ) AS stale_records
                """
            )
            counts = dict(cur.fetchone())
            for key, value in list(counts.items()):
                counts[key] = int(value or 0)

            if counts["conflict_reviews"] > 0:
                state = "conflict"
            elif counts["failed_jobs"] > 0 or counts["blocked_jobs"] > 0:
                state = "failed"
            elif counts["stale_records"] > 0 or counts["stale_reviews"] > 0:
                state = "stale"
            elif counts["pending_reviews"] > 0:
                state = "pending"
            else:
                state = "fresh"

            cur.execute(
                """
                SELECT id, review_type, target_type, target_id, review_status, updated_at
                FROM sync_reviews
                WHERE review_status IN ('pending', 'conflict', 'stale')
                ORDER BY updated_at DESC
                LIMIT 20
                """
            )
            review_items = [
                {
                    "kind": "review",
                    "id": str(row["id"]),
                    "review_type": row["review_type"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "state": row["review_status"],
                    "priority": "high" if row["review_status"] in ("conflict", "failed") else "normal",
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT id, job_type, target, status, updated_at, error_code, error_message
                FROM sync_jobs
                WHERE status IN ('failed', 'blocked')
                ORDER BY updated_at DESC
                LIMIT 20
                """
            )
            job_items = [
                {
                    "kind": "job",
                    "id": str(row["id"]),
                    "job_type": row["job_type"],
                    "target": row["target"],
                    "state": row["status"],
                    "priority": "high" if row["status"] in ("conflict", "failed") else "normal",
                    "error_code": row["error_code"] or "",
                    "error_message": row["error_message"] or "",
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in cur.fetchall()
            ]

            return {"state": state, "counts": counts, "items": review_items + job_items}
    finally:
        conn.close()


@router.patch("/sync/reviews/{review_id}")
def decide_sync_review(review_id: UUID, payload: SyncReviewDecision) -> dict:
    if payload.review_status not in DECISION_REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail="review_status must be accepted, rejected, merged, deferred, or conflict")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _review(cur, str(review_id))
            cur.execute(
                """
                UPDATE sync_reviews
                SET review_status = %(status)s,
                    decision = %(decision)s,
                    decided_at = now(),
                    updated_at = now()
                WHERE id = %(id)s
                """,
                {
                    "id": str(review_id),
                    "status": payload.review_status,
                    "decision": psycopg2.extras.Json(payload.decision),
                },
            )
            conn.commit()
            return _review(cur, str(review_id))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/sync/reviews/{review_id}/apply")
def apply_sync_review(review_id: UUID, payload: SyncReviewApplyRequest) -> dict:
    if not payload.is_confirmed():
        raise HTTPException(status_code=422, detail="confirmation must be true")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            review = _review(cur, str(review_id))
            if review["review_status"] not in {"accepted", "merged"}:
                raise HTTPException(status_code=409, detail="review must be accepted or merged before apply")
            if payload.target_surface and payload.target_surface != review["target_surface"]:
                raise HTTPException(status_code=409, detail="target_surface does not match review target")

            completed_result = _completed_apply_result(cur, review)
            if completed_result is not None:
                return completed_result

            job_id = _insert_apply_job(cur, review, payload.audit_payload(review))
            if review["review_type"] == "ticket_import" and review["target_type"] == "ticket":
                result = _apply_ticket_import(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            if review["review_type"] == "thread_import" and review["target_type"] == "thread":
                result = _apply_thread_import(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            if review["review_type"] == "relationship_change" and review["target_type"] == "relationship":
                result = _apply_relationship_change(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            if review["review_type"] == "vault_import" and review["target_type"] == "entity":
                result = _apply_vault_import(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            if review["review_type"] == "asset_import" and review["target_type"] == "asset":
                result = _apply_asset_import(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            if review["review_type"] == "npc_import" and review["target_type"] == "npc":
                result = _apply_npc_import(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            if review["review_type"] == "clock_mirror" and review["target_type"] == "clock":
                result = _apply_clock_mirror(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            if review["review_type"] == "clock_drift_adopt" and review["target_type"] == "clock":
                result = _apply_clock_drift_adopt(cur, review)
                result = _finish_apply_job(cur, job_id, result)
                conn.commit()
                return result

            message = f"apply is not implemented for review_type={review['review_type']}"
            cur.execute(
                """
                UPDATE sync_jobs
                SET status = 'blocked',
                    error = %(error)s,
                    error_code = 'unsupported_review_type',
                    error_message = %(error)s,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = %(id)s
                """,
                {"id": job_id, "error": message},
            )
            conn.commit()
            raise HTTPException(status_code=409, detail=message)
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
