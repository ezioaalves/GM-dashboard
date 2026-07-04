from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
import psycopg2.extras
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from . import services
from .db.get_db import get_connection, get_db
from .db.models import LoreAsset, LoreEntity, LoreRelationship, Scene, Session, Thread
from .system_enums import FRESHNESS_STATES, REVIEW_STATUSES, VISIBILITIES

router = APIRouter()


VALID_PRIORITIES = {"low", "med", "high", "urgent"}
STALE_AFTER_DAYS = 30
LEGACY_THREADS = Path("Campaign Management/authorial/threads")


def _source_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _legacy_status(status: str) -> str:
    return {
        "active": "active",
        "planted": "introduced",
        "introduced": "introduced",
        "paid": "resolved",
        "resolved": "resolved",
        "dormant": "dormant",
    }.get(status, "introduced")


def _parse_session_ref(value) -> int | None:
    if not isinstance(value, dict):
        return None
    session = value.get("session")
    return session if isinstance(session, int) else None


def _parse_datetime_ref(value) -> datetime | None:
    if not isinstance(value, dict):
        return None
    date_value = value.get("date")
    if not date_value:
        return None
    if isinstance(date_value, datetime):
        return date_value
    try:
        return datetime.fromisoformat(str(date_value))
    except ValueError:
        return None


def _parse_legacy_thread(path: Path, vault_root: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm, body = services.split_frontmatter(text, path)
    thread_id = str(fm.get("id") or path.stem)
    title = str(fm.get("title") or path.stem.replace("-", " ").title())
    status = _legacy_status(str(fm.get("status") or "introduced"))
    last_touched_session = _parse_session_ref(fm.get("last_touched"))
    introduced_session = _parse_session_ref(fm.get("introduced"))
    sessions = [value for value in [last_touched_session, introduced_session] if value is not None]
    return {
        "id": thread_id,
        "title": title,
        "status": status,
        "priority": "high" if status == "active" else "med",
        "arc": None,
        "theme": "",
        "pressure": "",
        "stakes": "",
        "next_move": str(fm.get("next_move") or "") or None,
        "clock_label": None,
        "clock_value": None,
        "clock_max": None,
        "unresolved_questions": [],
        "last_touched_at": _parse_datetime_ref(fm.get("last_touched")),
        "visibility": "gm",
        "freshness_state": "fresh",
        "review_status": "pending",
        "factions": [str(item) for item in fm.get("owners") or []],
        "sessions": sorted(set(sessions)),
        "vault_path": services.relative(vault_root, path),
        "body": body,
        "source_hash": _source_hash(text),
        "source_mtime": datetime.fromtimestamp(path.stat().st_mtime, UTC),
    }


class ThreadCreate(BaseModel):
    id: str
    title: str
    status: str = "active"
    priority: str = "med"
    arc: Optional[str] = None
    theme: str = ""
    pressure: str = ""
    stakes: str = ""
    next_move: Optional[str] = None
    clock_label: Optional[str] = None
    clock_value: Optional[int] = None
    clock_max: Optional[int] = None
    unresolved_questions: list[str] = []
    last_touched_at: Optional[datetime] = None
    visibility: str = "gm"
    freshness_state: str = "unknown"
    review_status: str = "accepted"
    factions: Optional[list[str]] = None
    sessions: Optional[list[int]] = None
    vault_path: Optional[str] = None
    body: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {value}")
        return value

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        if value not in VISIBILITIES:
            raise ValueError(f"Invalid visibility: {value}")
        return value

    @field_validator("freshness_state")
    @classmethod
    def validate_freshness(cls, value: str) -> str:
        if value not in FRESHNESS_STATES:
            raise ValueError(f"Invalid freshness_state: {value}")
        return value

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, value: str) -> str:
        if value not in REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status: {value}")
        return value


class ThreadPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    priority: str | None = None
    arc: str | None = None
    theme: str | None = None
    pressure: str | None = None
    stakes: str | None = None
    next_move: str | None = None
    clock_label: str | None = None
    clock_value: int | None = None
    clock_max: int | None = None
    unresolved_questions: list[str] | None = None
    last_touched_at: datetime | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    review_status: str | None = None
    factions: list[str] | None = None
    sessions: list[int] | None = None
    vault_path: str | None = None
    body: str | None = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {value}")
        return value

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str | None) -> str | None:
        if value is not None and value not in VISIBILITIES:
            raise ValueError(f"Invalid visibility: {value}")
        return value

    @field_validator("freshness_state")
    @classmethod
    def validate_freshness(cls, value: str | None) -> str | None:
        if value is not None and value not in FRESHNESS_STATES:
            raise ValueError(f"Invalid freshness_state: {value}")
        return value

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, value: str | None) -> str | None:
        if value is not None and value not in REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status: {value}")
        return value


def _thread_to_dict(thread: Thread) -> dict:
    data = {
        "id": thread.id,
        "graph_endpoint_id": thread.graph_endpoint_id or f"thread:{thread.id}",
        "title": thread.title,
        "status": thread.status,
        "priority": thread.priority or "med",
        "arc": thread.arc,
        "theme": thread.theme or "",
        "pressure": thread.pressure or "",
        "stakes": thread.stakes or "",
        "next_move": thread.next_move,
        "clock_label": thread.clock_label,
        "clock_value": thread.clock_value,
        "clock_max": thread.clock_max,
        "unresolved_questions": list(thread.unresolved_questions or []),
        "last_touched_at": thread.last_touched_at.isoformat() if thread.last_touched_at else None,
        "visibility": thread.visibility or "gm",
        "freshness_state": thread.freshness_state or "unknown",
        "review_status": thread.review_status or "accepted",
        "factions": list(thread.factions or []),
        "sessions": list(thread.sessions or []),
        "vault_path": thread.vault_path,
        "body": thread.body,
    }
    data["stale_state"] = _thread_stale_state(thread)
    return data


def _thread_stale_state(thread: Thread) -> dict:
    reasons: list[str] = []
    state = "current"
    age_days = None
    if thread.last_touched_at:
        touched = thread.last_touched_at
        if touched.tzinfo is None:
            touched = touched.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - touched).days
        if age_days > STALE_AFTER_DAYS:
            reasons.append("last_touched_stale")
    elif thread.status == "active":
        reasons.append("never_touched")

    if thread.freshness_state not in {"fresh", "unknown"}:
        reasons.append(thread.freshness_state)
    if thread.status == "active" and not (thread.next_move or "").strip():
        reasons.append("missing_next_move")

    if any(reason in reasons for reason in {"stale_source_changed", "stale_db_newer", "missing_source", "conflict"}):
        state = "stale"
    elif "last_touched_stale" in reasons or "never_touched" in reasons:
        state = "stale"
    elif "missing_next_move" in reasons:
        state = "needs_direction"

    return {"state": state, "age_days": age_days, "reasons": reasons}


def _get_thread_or_404(db: DBSession, thread_id: str) -> Thread:
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    return thread


def _raw_endpoint_id(endpoint_id: str) -> str:
    return endpoint_id.split(":", 1)[1] if ":" in endpoint_id else endpoint_id


def _entity_summary(entity: LoreEntity) -> dict:
    return {
        "id": str(entity.id),
        "graph_endpoint_id": entity.graph_endpoint_id or f"entity:{entity.id}",
        "slug": entity.slug,
        "title": entity.title,
        "entity_type": entity.entity_type,
        "summary": entity.summary or "",
        "freshness_state": entity.freshness_state or "unknown",
    }


def _session_summary(session: Session) -> dict:
    return {
        "id": session.id,
        "graph_endpoint_id": session.graph_endpoint_id or f"session:{session.id}",
        "number": session.number,
        "name": session.name or "",
        "status": session.status,
        "date": session.date.isoformat() if session.date else None,
        "freshness_state": session.freshness_state or "unknown",
    }


def _scene_summary(scene: Scene) -> dict:
    return {
        "id": scene.id,
        "graph_endpoint_id": scene.graph_endpoint_id or f"scene:{scene.id}",
        "title": scene.title,
        "status": scene.status,
        "session_id": scene.session_id,
        "placement": scene.placement or "backlog",
        "purpose": scene.purpose or "",
        "freshness_state": scene.freshness_state or "unknown",
    }


def _asset_summary(asset: LoreAsset) -> dict:
    return {
        "id": str(asset.id),
        "graph_endpoint_id": asset.graph_endpoint_id or f"asset:{asset.id}",
        "title": asset.title,
        "asset_type": asset.asset_type,
        "usage": asset.usage,
        "status": asset.status,
        "freshness_state": asset.freshness_state or "unknown",
    }


def _relationship_to_dict(relationship: LoreRelationship) -> dict:
    return {
        "id": str(relationship.id),
        "source_type": relationship.source_type,
        "source_id": relationship.source_id,
        "target_type": relationship.target_type,
        "target_id": relationship.target_id,
        "unresolved_target": relationship.unresolved_target,
        "relationship_type": relationship.relationship_type,
        "direction": relationship.direction,
        "provenance": relationship.provenance,
        "confidence": relationship.confidence,
        "context": relationship.context or "",
        "review_status": relationship.review_status or "pending",
    }


def _thread_detail_to_dict(db: DBSession, thread: Thread) -> dict:
    detail = _thread_to_dict(thread)
    thread_endpoint = detail["graph_endpoint_id"]
    relationships = (
        db.query(LoreRelationship)
        .filter(
            or_(
                (LoreRelationship.source_type == "thread") & (LoreRelationship.source_id == thread_endpoint),
                (LoreRelationship.target_type == "thread") & (LoreRelationship.target_id == thread_endpoint),
            )
        )
        .order_by(LoreRelationship.created_at.desc())
        .all()
    )

    entity_ids: set[str] = set()
    session_ids: set[int] = set(thread.sessions or [])
    scene_ids: set[int] = set()
    asset_ids: set[str] = set()
    for relationship in relationships:
        pairs = [
            (relationship.source_type, relationship.source_id),
            (relationship.target_type, relationship.target_id),
        ]
        for endpoint_type, endpoint_id in pairs:
            if not endpoint_id:
                continue
            raw_id = _raw_endpoint_id(endpoint_id)
            if endpoint_type == "entity":
                entity_ids.add(endpoint_id if endpoint_id.startswith("entity:") else f"entity:{raw_id}")
            elif endpoint_type == "session" and raw_id.isdigit():
                session_ids.add(int(raw_id))
            elif endpoint_type == "scene" and raw_id.isdigit():
                scene_ids.add(int(raw_id))
            elif endpoint_type == "asset":
                asset_ids.add(endpoint_id if endpoint_id.startswith("asset:") else f"asset:{raw_id}")

    entities = []
    if entity_ids:
        entities = (
            db.query(LoreEntity)
            .filter(LoreEntity.graph_endpoint_id.in_(entity_ids))
            .order_by(LoreEntity.title.asc())
            .all()
        )
    sessions = []
    if session_ids:
        sessions = (
            db.query(Session)
            .filter(or_(Session.id.in_(session_ids), Session.number.in_(session_ids)))
            .order_by(Session.number.asc())
            .all()
        )
    scenes = []
    if scene_ids:
        scenes = db.query(Scene).filter(Scene.id.in_(scene_ids)).order_by(Scene.id.asc()).all()
    assets = []
    if asset_ids:
        assets = (
            db.query(LoreAsset)
            .filter(LoreAsset.graph_endpoint_id.in_(asset_ids))
            .order_by(LoreAsset.title.asc())
            .all()
        )

    detail["linked"] = {
        "entities": [_entity_summary(entity) for entity in entities],
        "sessions": [_session_summary(session) for session in sessions],
        "scenes": [_scene_summary(scene) for scene in scenes],
        "assets": [_asset_summary(asset) for asset in assets],
        "relationships": [_relationship_to_dict(relationship) for relationship in relationships],
    }
    return detail


def _thread_summary_payload(db: DBSession) -> dict:
    threads = db.query(Thread).all()
    stale = [thread for thread in threads if _thread_stale_state(thread)["state"] == "stale"]
    needs_direction = [
        thread for thread in threads if _thread_stale_state(thread)["state"] == "needs_direction"
    ]
    active = [thread for thread in threads if thread.status == "active"]
    urgent = [thread for thread in threads if thread.priority in {"high", "urgent"}]
    next_moves = [
        _thread_to_dict(thread)
        for thread in sorted(
            [thread for thread in active if (thread.next_move or "").strip()],
            key=lambda item: (item.priority != "urgent", item.priority != "high", item.updated_at),
        )[:5]
    ]
    return {
        "total": len(threads),
        "active": len(active),
        "stale": len(stale),
        "needs_direction": len(needs_direction),
        "high_priority": len(urgent),
        "next_moves": next_moves,
        "next_campaign_move": next_moves[0] if next_moves else None,
        "active_pressure": [_thread_to_dict(thread) for thread in urgent[:5]],
        "stale_threads": [_thread_to_dict(thread) for thread in stale[:5]],
    }


@router.post("/threads/import/review", status_code=201)
def stage_legacy_thread_import_reviews() -> dict:
    vault_root = services.find_vault_root()
    threads_dir = vault_root / LEGACY_THREADS
    if not threads_dir.exists():
        return {"review_type": "thread_import", "found": 0, "created": [], "skipped": [], "errors": []}

    parsed: list[dict] = []
    errors: list[str] = []
    for path in sorted(threads_dir.glob("*.md")):
        if path.name.startswith("_") or "_drafts" in path.parts:
            continue
        try:
            parsed.append(_parse_legacy_thread(path, vault_root))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    conn = get_connection()
    created: list[dict] = []
    skipped: list[dict] = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for thread in parsed:
                cur.execute(
                    """
                    SELECT id
                    FROM sync_reviews
                    WHERE review_type = 'thread_import'
                      AND target_type = 'thread'
                      AND target_id = %s
                      AND current_version = %s
                      AND review_status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (thread["id"], thread["source_hash"]),
                )
                existing = cur.fetchone()
                if existing:
                    skipped.append({"thread_id": thread["id"], "review_id": str(existing["id"])})
                    continue

                cur.execute(
                    """
                    UPDATE sync_reviews
                    SET review_status = 'stale', updated_at = now()
                    WHERE review_type = 'thread_import'
                      AND target_type = 'thread'
                      AND target_id = %s
                      AND review_status = 'pending'
                    """,
                    (thread["id"],),
                )
                cur.execute(
                    """
                    INSERT INTO sync_reviews (
                      review_type, source_surface, target_surface, target_type, target_id,
                      base_version, current_version, proposed_changes, review_status
                    )
                    VALUES (
                      'thread_import', 'vault', 'postgres', 'thread', %(target_id)s,
                      '', %(current_version)s, %(proposed_changes)s, 'pending'
                    )
                    RETURNING id
                    """,
                    {
                        "target_id": thread["id"],
                        "current_version": thread["source_hash"],
                        "proposed_changes": psycopg2.extras.Json(
                            {
                                "action": "import_thread",
                                "thread": {
                                    key: value.isoformat() if isinstance(value, datetime) else value
                                    for key, value in thread.items()
                                },
                                "source_preserved": True,
                            }
                        ),
                    },
                )
                created.append({"thread_id": thread["id"], "review_id": str(cur.fetchone()["id"])})
    finally:
        conn.close()

    return {
        "review_type": "thread_import",
        "found": len(parsed),
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "source_files_deleted": 0,
    }


@router.get("/threads")
def list_threads(
    status: str | None = None,
    arc: str | None = None,
    priority: str | None = None,
    freshness_state: str | None = None,
    q: str | None = None,
    db: DBSession = Depends(get_db),
) -> list[dict]:
    query = db.query(Thread)
    if status:
        query = query.filter(Thread.status == status)
    if arc:
        query = query.filter(Thread.arc == arc)
    if priority:
        query = query.filter(Thread.priority == priority)
    if freshness_state:
        query = query.filter(Thread.freshness_state == freshness_state)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            Thread.title.ilike(pattern)
            | Thread.id.ilike(pattern)
            | Thread.pressure.ilike(pattern)
            | Thread.stakes.ilike(pattern)
            | Thread.next_move.ilike(pattern)
        )
    return [
        _thread_to_dict(thread)
        for thread in query.order_by(Thread.priority.desc(), Thread.updated_at.desc()).all()
    ]


@router.get("/threads/summary")
def thread_summary(db: DBSession = Depends(get_db)) -> dict:
    return _thread_summary_payload(db)


@router.get("/cockpit/thread-direction")
def cockpit_thread_direction(db: DBSession = Depends(get_db)) -> dict:
    return _thread_summary_payload(db)


@router.post("/threads", status_code=201)
def create_thread(payload: ThreadCreate, db: DBSession = Depends(get_db)) -> dict:
    thread = Thread(**payload.model_dump())
    db.add(thread)
    try:
        db.commit()
        db.refresh(thread)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Thread {payload.id} already exists")
    return _thread_to_dict(thread)


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str, db: DBSession = Depends(get_db)) -> dict:
    return _thread_detail_to_dict(db, _get_thread_or_404(db, thread_id))


@router.patch("/threads/{thread_id}")
def patch_thread(thread_id: str, payload: ThreadPatch, db: DBSession = Depends(get_db)) -> dict:
    thread = _get_thread_or_404(db, thread_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(thread, field, value)
    db.commit()
    db.refresh(thread)
    return _thread_to_dict(thread)
