from __future__ import annotations

from datetime import date as Date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError

import psycopg2.extras

from .db.get_db import get_connection, get_db
from .db.models import Session, Scene, SessionNote, SessionAdventure, Adventure
from .services import find_vault_root, slugify
from .session_scan import scan_sessions
from .system_enums import FRESHNESS_STATES, REVIEW_STATUSES, SESSION_STATUSES, VISIBILITIES

router = APIRouter()

LEGACY_STATUS_ALIASES = {
    "Planned": "planned",
    "Active": "ready",
    "Played": "played",
}
VALID_STATUSES = set(SESSION_STATUSES) | set(LEGACY_STATUS_ALIASES)
CLUE_TIERS = {"core", "superior", "optional", "false-lead", "back-door"}


def normalize_session_status(value: str) -> str:
    return LEGACY_STATUS_ALIASES.get(value, value)


class ClueMapEntry(BaseModel):
    tier: str
    text: str = ""
    holder: str = ""
    location: str = ""
    found: bool = False
    scene_ids: list[int] = Field(default_factory=list)
    notes: str = ""

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        if v not in CLUE_TIERS:
            raise ValueError(f"Invalid clue tier: {v}")
        return v

    @field_validator("scene_ids")
    @classmethod
    def validate_scene_ids(cls, v: list[int]) -> list[int]:
        if any(scene_id < 1 for scene_id in v):
            raise ValueError("scene_ids must be positive")
        return v

    @model_validator(mode="after")
    def validate_content(self) -> "ClueMapEntry":
        if not self.text.strip():
            raise ValueError("Clue text is required")
        if not self.holder.strip() and not self.location.strip():
            raise ValueError("Clue holder or location is required")
        return self


class SessionCreate(BaseModel):
    number: int
    name: str = ""
    status: str = "Planned"
    date: Optional[Date] = None
    notes: str = ""
    promise: str = ""
    fit_check: dict[str, Any] = Field(default_factory=dict)
    clue_map: list[ClueMapEntry] = Field(default_factory=list)
    wrap_capture: dict[str, Any] = Field(default_factory=dict)
    recap_seed: str = ""
    prep_notes: str = ""
    wrap_notes: str = ""

    @field_validator("number")
    @classmethod
    def validate_number(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Session number must be positive")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return normalize_session_status(v)


class SessionUpdate(SessionCreate):
    pass


class SessionPatch(BaseModel):
    number: int | None = None
    name: str | None = None
    status: str | None = None
    date: Optional[Date] = None
    notes: str | None = None
    summary: str | None = None
    promise: str | None = None
    fit_check: dict[str, Any] | None = None
    clue_map: list[ClueMapEntry] | None = None
    wrap_capture: dict[str, Any] | None = None
    recap_seed: str | None = None
    prep_notes: str | None = None
    wrap_notes: str | None = None
    source_path: str | None = None
    source_hash: str | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    review_status: str | None = None

    @field_validator("number")
    @classmethod
    def validate_number(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("Session number must be positive")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return normalize_session_status(v) if v is not None else None

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str | None) -> str | None:
        if v is not None and v not in VISIBILITIES:
            raise ValueError(f"Invalid visibility: {v}")
        return v

    @field_validator("freshness_state")
    @classmethod
    def validate_freshness_state(cls, v: str | None) -> str | None:
        if v is not None and v not in FRESHNESS_STATES:
            raise ValueError(f"Invalid freshness_state: {v}")
        return v

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, v: str | None) -> str | None:
        if v is not None and v not in REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status: {v}")
        return v


class SessionStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return normalize_session_status(v)


class SessionNotePayload(BaseModel):
    scenes: list[str] = []
    npcs_present: list[str] = []
    clues_discovered: list[str] = []
    threads_touched: list[str] = []
    unresolved_questions: list[str] = []
    next_session_hook: str = ""
    memory: str = ""
    markdown: str = ""
    target_path: str = ""
    status: str = "draft"


class SceneOrderPayload(BaseModel):
    ordered_scene_ids: list[int] = []
    floating_scene_ids: list[int] = []
    backlog_scene_ids: list[int] = []


def _scene_to_summary(scene: Scene) -> dict:
    return {
        "id": scene.id,
        "graph_endpoint_id": scene.graph_endpoint_id or f"scene:{scene.id}",
        "title": scene.title,
        "type": scene.type,
        "status": scene.status,
        "session_id": scene.session_id,
        "placement": scene.placement or "backlog",
        "sort_order": scene.sort_order or 0,
        "purpose": scene.purpose or "",
        "entry_pressure": scene.entry_pressure or "",
        "exit_condition": scene.exit_condition or "",
        "freshness_state": scene.freshness_state or "unknown",
        "review_status": scene.review_status or "accepted",
    }


def _session_to_dict(session: Session, scene_count: int, adventures: list[dict] | None = None) -> dict:
    return {
        "id": session.id,
        "graph_endpoint_id": session.graph_endpoint_id or f"session:{session.id}",
        "number": session.number,
        "name": session.name,
        "status": session.status,
        "date": session.date.isoformat() if session.date else None,
        "notes": session.notes or "",
        "summary": session.summary or "",
        "promise": session.promise or "",
        "fit_check": session.fit_check or {},
        "clue_map": session.clue_map or [],
        "wrap_capture": session.wrap_capture or {},
        "recap_seed": session.recap_seed or "",
        "prep_notes": session.prep_notes or "",
        "wrap_notes": session.wrap_notes or "",
        "source_path": session.source_path or "",
        "source_hash": session.source_hash or "",
        "visibility": session.visibility or "gm",
        "freshness_state": session.freshness_state or "unknown",
        "review_status": session.review_status or "accepted",
        "scene_count": scene_count,
        "adventures": adventures or [],
    }


def _session_adventures(db: DBSession, session_id: int) -> list[dict]:
    rows = (
        db.query(Adventure)
        .join(SessionAdventure, SessionAdventure.adventure_id == Adventure.id)
        .filter(SessionAdventure.session_id == session_id)
        .order_by(Adventure.id.asc())
        .all()
    )
    return [{"id": a.id, "title": a.title} for a in rows]


def _session_detail_to_dict(db: DBSession, session: Session) -> dict:
    detail = _session_to_dict(session, len(session.scenes or []), _session_adventures(db, session.id))
    scenes = (
        db.query(Scene)
        .filter(Scene.session_id == session.id)
        .order_by(Scene.placement.asc(), Scene.sort_order.asc(), Scene.id.asc())
        .all()
    )
    ordered = [scene for scene in scenes if scene.placement == "ordered"]
    floating = [scene for scene in scenes if scene.placement == "floating"]
    backlog = [scene for scene in scenes if scene.placement == "backlog"]
    detail["scenes"] = {
        "ordered": [_scene_to_summary(scene) for scene in ordered],
        "floating": [_scene_to_summary(scene) for scene in floating],
        "backlog": [_scene_to_summary(scene) for scene in backlog],
    }
    return detail


def _serialize_clue_map(clue_map: list[ClueMapEntry | dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry.model_dump() if isinstance(entry, ClueMapEntry) else entry for entry in clue_map]


def _render_wrap_recap_seed(session: Session, wrap_capture: dict[str, Any]) -> str:
    if not wrap_capture:
        return ""
    parts: list[str] = []
    actual_endpoint = str(wrap_capture.get("actual_endpoint") or "").strip()
    next_hook = str(wrap_capture.get("next_session_hook") or "").strip()
    rewards = str(wrap_capture.get("rewards") or "").strip()
    clock_movement = str(wrap_capture.get("clock_movement") or "").strip()
    lane_changes = str(wrap_capture.get("lane_changes") or "").strip()

    if actual_endpoint:
        parts.append(f"Last endpoint: {actual_endpoint}")
    if next_hook:
        parts.append(f"Opening hook: {next_hook}")
    if rewards:
        parts.append(f"Rewards: {rewards}")
    if clock_movement:
        parts.append(f"Clock movement: {clock_movement}")
    if lane_changes:
        parts.append(f"Lane changes: {lane_changes}")
    if not parts:
        return ""
    return f"Session {session.number} wrap bridge. " + " ".join(parts)


def _prefill_next_session_recap(db: DBSession, session: Session) -> None:
    seed = _render_wrap_recap_seed(session, session.wrap_capture or {})
    if not seed:
        return
    next_session = (
        db.query(Session)
        .filter(Session.number > session.number)
        .order_by(Session.number.asc())
        .first()
    )
    if next_session and not (next_session.recap_seed or "").strip():
        next_session.recap_seed = seed


def _note_to_dict(note: SessionNote) -> dict:
    return {
        "id": note.id,
        "session_id": note.session_id,
        "scenes": list(note.scenes or []),
        "npcs_present": list(note.npcs_present or []),
        "clues_discovered": list(note.clues_discovered or []),
        "threads_touched": list(note.threads_touched or []),
        "unresolved_questions": list(note.unresolved_questions or []),
        "next_session_hook": note.next_session_hook or "",
        "memory": note.memory or "",
        "markdown": note.markdown or "",
        "target_path": note.target_path or "",
        "status": note.status or "draft",
    }


def _render_list(items: list[str], todo: str) -> str:
    if not items:
        return f"<!-- TODO: {todo} -->"
    return "\n".join(f"- {item}" for item in items)


def _render_numbered(items: list[str], todo: str) -> str:
    if not items:
        return f"<!-- TODO: {todo} -->"
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(items, start=1))


def _yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(items) + "]"


def _render_session_note_markdown(session: Session, payload: SessionNotePayload) -> tuple[str, str]:
    title = session.name or f"Session {session.number}"
    date_value = session.date.isoformat() if session.date else ""
    safe_title = title.replace('"', '\\"')
    markdown = f"""---
schema_version: 1
session: {session.number}
date: {date_value}
title: "{safe_title}"
poles_advanced: []
threads:
  advanced: []
  planted: []
  resolved: []
npcs_present: {_yaml_list(payload.npcs_present)}
locations: []
has_secret: false
---

# Session {session.number} - {title}

## What happened

{_render_numbered(payload.scenes, "add scene summaries, one per line")}

## NPCs in play

{_render_list(payload.npcs_present, "list NPCs present")}

## Clues discovered

{_render_list(payload.clues_discovered, "list clues discovered")}

## Threads touched

{_render_list(payload.threads_touched, "list threads/clocks touched")}

## Unresolved questions

{_render_list(payload.unresolved_questions, "list unresolved questions")}

## Hook for next session

{payload.next_session_hook.strip() if payload.next_session_hook.strip() else "<!-- TODO: set next-session hook -->"}

## Continuity notes

{payload.memory.strip() if payload.memory.strip() else "<!-- TODO: add GM continuity notes -->"}

## Notable moments

<!-- TODO: add table moments -->
"""
    target = payload.target_path or f"Campaign Management/session-logs/{session.number:02d}-{slugify(title)}.md"
    return markdown, target


def _get_session_or_404(db: DBSession, session_id: int) -> Session:
    """Retrieve a session or raise 404."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


def _get_scenes_by_ids_or_404(db: DBSession, scene_ids: list[int]) -> dict[int, Scene]:
    if not scene_ids:
        return {}
    scenes = db.query(Scene).filter(Scene.id.in_(scene_ids)).all()
    by_id = {scene.id: scene for scene in scenes}
    missing = sorted(set(scene_ids) - set(by_id))
    if missing:
        raise HTTPException(status_code=404, detail=f"Scenes not found: {missing}")
    return by_id


@router.get("/sessions")
def list_sessions(db: DBSession = Depends(get_db)) -> list[dict]:
    """
    List all sessions with scene count (LEFT JOIN to scenes).
    """
    sessions = db.query(Session).order_by(Session.number.desc()).all()

    result = []
    for session in sessions:
        scene_count = db.query(func.count(Scene.id)).filter(
            Scene.session_id == session.id
        ).scalar() or 0
        result.append(_session_to_dict(session, scene_count))

    return result


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: DBSession = Depends(get_db)) -> dict:
    session = _get_session_or_404(db, session_id)
    return _session_detail_to_dict(db, session)


@router.post("/sessions", status_code=201)
def create_session(payload: SessionCreate, db: DBSession = Depends(get_db)) -> dict:
    """Create a new session."""
    new_session = Session(
        number=payload.number,
        name=payload.name,
        status=payload.status,
        date=payload.date,
        notes=payload.notes,
        promise=payload.promise,
        fit_check=payload.fit_check,
        clue_map=_serialize_clue_map(payload.clue_map),
        wrap_capture=payload.wrap_capture,
        recap_seed=payload.recap_seed,
        prep_notes=payload.prep_notes,
        wrap_notes=payload.wrap_notes,
    )
    db.add(new_session)
    try:
        db.commit()
        db.refresh(new_session)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Session {payload.number} already exists")

    return _session_to_dict(new_session, 0)


@router.patch("/sessions/{session_id}")
def patch_session(session_id: int, payload: SessionPatch, db: DBSession = Depends(get_db)) -> dict:
    session = _get_session_or_404(db, session_id)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        if field == "clue_map":
            value = _serialize_clue_map(value)
        setattr(session, field, value)
    if "wrap_capture" in values or values.get("status") == "played":
        _prefill_next_session_recap(db, session)

    try:
        db.commit()
        db.refresh(session)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Session {payload.number} already exists")

    scene_count = db.query(func.count(Scene.id)).filter(
        Scene.session_id == session.id
    ).scalar() or 0
    return _session_to_dict(session, scene_count)


@router.put("/sessions/{session_id}")
def update_session(session_id: int, payload: SessionUpdate, db: DBSession = Depends(get_db)) -> dict:
    """Update session fields."""
    session = _get_session_or_404(db, session_id)

    session.number = payload.number
    session.name = payload.name
    session.status = payload.status
    session.date = payload.date
    session.notes = payload.notes
    session.promise = payload.promise
    session.fit_check = payload.fit_check
    session.clue_map = _serialize_clue_map(payload.clue_map)
    session.wrap_capture = payload.wrap_capture
    session.recap_seed = payload.recap_seed
    session.prep_notes = payload.prep_notes
    session.wrap_notes = payload.wrap_notes
    _prefill_next_session_recap(db, session)

    try:
        db.commit()
        db.refresh(session)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Session {payload.number} already exists")

    scene_count = db.query(func.count(Scene.id)).filter(
        Scene.session_id == session.id
    ).scalar() or 0

    return _session_to_dict(session, scene_count)


@router.patch("/sessions/{session_id}/status")
def patch_session_status(
    session_id: int,
    payload: SessionStatusUpdate,
    db: DBSession = Depends(get_db),
) -> dict:
    """
    Update only session status (Planned → Active → Played).
    """
    session = _get_session_or_404(db, session_id)
    session.status = payload.status
    if payload.status == "played":
        _prefill_next_session_recap(db, session)

    db.commit()
    db.refresh(session)

    return {"id": session.id, "status": session.status}


@router.post("/sessions/{session_id}/scene-order")
def replace_session_scene_order(
    session_id: int,
    payload: SceneOrderPayload,
    db: DBSession = Depends(get_db),
) -> dict:
    session = _get_session_or_404(db, session_id)
    ordered_ids = payload.ordered_scene_ids
    floating_ids = payload.floating_scene_ids
    backlog_ids = payload.backlog_scene_ids
    all_ids = ordered_ids + floating_ids + backlog_ids
    if len(all_ids) != len(set(all_ids)):
        raise HTTPException(status_code=422, detail="Scene ids may appear in only one placement")

    scenes_by_id = _get_scenes_by_ids_or_404(db, all_ids)

    current_session_scenes = db.query(Scene).filter(Scene.session_id == session.id).all()
    listed = set(all_ids)
    for scene in current_session_scenes:
        if scene.id not in listed:
            scene.session_id = None
            scene.placement = "backlog"
            scene.sort_order = 0

    for sort_order, scene_id in enumerate(ordered_ids):
        scene = scenes_by_id[scene_id]
        scene.session_id = session.id
        scene.placement = "ordered"
        scene.sort_order = sort_order

    for sort_order, scene_id in enumerate(floating_ids):
        scene = scenes_by_id[scene_id]
        scene.session_id = session.id
        scene.placement = "floating"
        scene.sort_order = sort_order

    for sort_order, scene_id in enumerate(backlog_ids):
        scene = scenes_by_id[scene_id]
        scene.session_id = None
        scene.placement = "backlog"
        scene.sort_order = sort_order

    db.commit()
    db.refresh(session)
    return _session_detail_to_dict(db, session)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: DBSession = Depends(get_db)) -> dict:
    """Delete a session."""
    session = _get_session_or_404(db, session_id)
    for scene in db.query(Scene).filter(Scene.session_id == session.id).all():
        scene.session_id = None
        scene.placement = "backlog"
        scene.sort_order = 0
    db.delete(session)
    db.commit()
    return {"deleted": True}


@router.get("/sessions/{session_id}/note")
def get_session_note(session_id: int, db: DBSession = Depends(get_db)) -> dict | None:
    """Retrieve session notes."""
    _get_session_or_404(db, session_id)
    note = db.query(SessionNote).filter(SessionNote.session_id == session_id).first()
    return _note_to_dict(note) if note else None


@router.put("/sessions/{session_id}/note")
def upsert_session_note(
    session_id: int,
    payload: SessionNotePayload,
    db: DBSession = Depends(get_db),
) -> dict:
    """Create or update session notes."""
    session = _get_session_or_404(db, session_id)

    note = db.query(SessionNote).filter(SessionNote.session_id == session_id).first()
    if note:
        note.scenes = payload.scenes
        note.npcs_present = payload.npcs_present
        note.clues_discovered = payload.clues_discovered
        note.threads_touched = payload.threads_touched
        note.unresolved_questions = payload.unresolved_questions
        note.next_session_hook = payload.next_session_hook
        note.memory = payload.memory
        note.markdown = payload.markdown
        note.target_path = payload.target_path
        note.status = payload.status
    else:
        note = SessionNote(
            session_id=session_id,
            scenes=payload.scenes,
            npcs_present=payload.npcs_present,
            clues_discovered=payload.clues_discovered,
            threads_touched=payload.threads_touched,
            unresolved_questions=payload.unresolved_questions,
            next_session_hook=payload.next_session_hook,
            memory=payload.memory,
            markdown=payload.markdown,
            target_path=payload.target_path,
            status=payload.status,
        )
        db.add(note)

    db.commit()
    db.refresh(note)
    return _note_to_dict(note)


@router.post("/sessions/{session_id}/note/generate")
def generate_session_note(
    session_id: int,
    payload: SessionNotePayload,
    db: DBSession = Depends(get_db),
) -> dict:
    """Generate session notes from template."""
    session = _get_session_or_404(db, session_id)
    markdown, target_path = _render_session_note_markdown(session, payload)

    next_payload = payload.model_copy(
        update={
            "markdown": markdown,
            "target_path": target_path,
            "status": "draft",
        }
    )

    note = db.query(SessionNote).filter(SessionNote.session_id == session_id).first()
    if note:
        note.scenes = next_payload.scenes
        note.npcs_present = next_payload.npcs_present
        note.clues_discovered = next_payload.clues_discovered
        note.threads_touched = next_payload.threads_touched
        note.unresolved_questions = next_payload.unresolved_questions
        note.next_session_hook = next_payload.next_session_hook
        note.memory = next_payload.memory
        note.markdown = next_payload.markdown
        note.target_path = next_payload.target_path
        note.status = next_payload.status
    else:
        note = SessionNote(
            session_id=session_id,
            scenes=next_payload.scenes,
            npcs_present=next_payload.npcs_present,
            clues_discovered=next_payload.clues_discovered,
            threads_touched=next_payload.threads_touched,
            unresolved_questions=next_payload.unresolved_questions,
            next_session_hook=next_payload.next_session_hook,
            memory=next_payload.memory,
            markdown=next_payload.markdown,
            target_path=next_payload.target_path,
            status=next_payload.status,
        )
        db.add(note)

    db.commit()
    db.refresh(note)
    return _note_to_dict(note)


@router.post("/sessions/import/scan")
def scan_sessions_import(dry_run: bool = False) -> dict:
    vault_root = find_vault_root()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            summary = scan_sessions(vault_root, cur, dry_run=dry_run)
            if not dry_run:
                conn.commit()
            return summary
    finally:
        conn.close()
