from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .db.get_db import get_connection

router = APIRouter()

REVIEW_STATUSES = {"pending", "accepted", "rejected", "merged", "deferred", "conflict", "stale"}


class SyncReviewDecision(BaseModel):
    review_status: str
    decision: dict[str, Any] = {}


class SyncReviewApplyRequest(BaseModel):
    confirm: bool = False


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


def _insert_apply_job(cur, review: dict) -> str:
    cur.execute(
        """
        INSERT INTO sync_jobs (
          target, direction, status, diff, job_type,
          source_surface, target_surface, payload, started_at, updated_at
        )
        VALUES (
          %(target)s, %(direction)s, 'running', '', 'apply_review',
          %(source_surface)s, %(target_surface)s, %(payload)s, now(), now()
        )
        RETURNING id
        """,
        {
            "target": f"{review['target_type']}:{review['target_id']}",
            "direction": f"{review['source_surface']}_to_{review['target_surface']}",
            "source_surface": review["source_surface"],
            "target_surface": review["target_surface"],
            "payload": psycopg2.extras.Json(
                {
                    "review_id": review["id"],
                    "review_type": review["review_type"],
                    "target_type": review["target_type"],
                    "target_id": review["target_id"],
                }
            ),
        },
    )
    job_id = str(cur.fetchone()["id"])
    cur.execute(
        "UPDATE sync_reviews SET sync_job_id = %s, updated_at = now() WHERE id = %s",
        (job_id, review["id"]),
    )
    return job_id


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


@router.get("/sync/reviews/{review_id}")
def get_sync_review(review_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return _review(cur, str(review_id))
    finally:
        conn.close()


@router.patch("/sync/reviews/{review_id}")
def decide_sync_review(review_id: UUID, payload: SyncReviewDecision) -> dict:
    if payload.review_status not in REVIEW_STATUSES - {"pending", "stale"}:
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
    if payload.confirm is not True:
        raise HTTPException(status_code=422, detail="confirm must be true")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            review = _review(cur, str(review_id))
            if review["review_status"] not in {"accepted", "merged"}:
                raise HTTPException(status_code=409, detail="review must be accepted or merged before apply")
            job_id = _insert_apply_job(cur, review)
            if review["review_type"] == "ticket_import" and review["target_type"] == "ticket":
                result = _apply_ticket_import(cur, review)
                cur.execute(
                    """
                    UPDATE sync_jobs
                    SET status = 'succeeded',
                        result = %(result)s,
                        finished_at = now(),
                        updated_at = now()
                    WHERE id = %(id)s
                    """,
                    {"id": job_id, "result": psycopg2.extras.Json(result)},
                )
                conn.commit()
                return result

            message = f"apply is not implemented for review_type={review['review_type']}"
            cur.execute(
                """
                UPDATE sync_jobs
                SET status = 'blocked',
                    error = %(error)s,
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
