from __future__ import annotations

from datetime import date as Date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError

from .db.get_db import get_db
from .db.models import Session, Scene, SessionNote
from .services import slugify

router = APIRouter()

VALID_STATUSES = {"Planned", "Active", "Played"}


class SessionCreate(BaseModel):
    number: int
    name: str = ""
    status: str = "Planned"
    date: Optional[Date] = None
    notes: str = ""

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
        return v


class SessionUpdate(SessionCreate):
    pass


class SessionStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


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


def _session_to_dict(session: Session, scene_count: int) -> dict:
    return {
        "id": session.id,
        "number": session.number,
        "name": session.name,
        "status": session.status,
        "date": session.date.isoformat() if session.date else None,
        "notes": session.notes or "",
        "scene_count": scene_count,
    }


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


@router.post("/sessions", status_code=201)
def create_session(payload: SessionCreate, db: DBSession = Depends(get_db)) -> dict:
    """Create a new session."""
    new_session = Session(
        number=payload.number,
        name=payload.name,
        status=payload.status,
        date=payload.date,
        notes=payload.notes,
    )
    db.add(new_session)
    try:
        db.commit()
        db.refresh(new_session)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Session {payload.number} already exists")

    return _session_to_dict(new_session, 0)


@router.put("/sessions/{session_id}")
def update_session(session_id: int, payload: SessionUpdate, db: DBSession = Depends(get_db)) -> dict:
    """Update session fields."""
    session = _get_session_or_404(db, session_id)

    session.number = payload.number
    session.name = payload.name
    session.status = payload.status
    session.date = payload.date
    session.notes = payload.notes

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

    db.commit()
    db.refresh(session)

    return {"id": session.id, "status": session.status}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: DBSession = Depends(get_db)) -> dict:
    """Delete a session."""
    session = _get_session_or_404(db, session_id)
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
