from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import Thread
from .system_enums import FRESHNESS_STATES, REVIEW_STATUSES, VISIBILITIES

router = APIRouter()


VALID_PRIORITIES = {"low", "med", "high", "urgent"}


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
    return {
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


def _get_thread_or_404(db: DBSession, thread_id: str) -> Thread:
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    return thread


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
    return _thread_to_dict(_get_thread_or_404(db, thread_id))


@router.patch("/threads/{thread_id}")
def patch_thread(thread_id: str, payload: ThreadPatch, db: DBSession = Depends(get_db)) -> dict:
    thread = _get_thread_or_404(db, thread_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(thread, field, value)
    db.commit()
    db.refresh(thread)
    return _thread_to_dict(thread)
