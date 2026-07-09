from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import FeedbackActionItem, FeedbackEntry, Session

router = APIRouter()

VALID_CADENCES = {"quick_check", "arc_review", "private_checkin"}
VALID_ACTION_ITEM_STATUSES = {"open", "done", "dropped"}

# Approximate GM cadence thresholds (in sessions since the last matching entry).
# private_checkin has no cadence and is never considered overdue.
OVERDUE_THRESHOLDS = {"quick_check": 4, "arc_review": 8}


class FeedbackEntryCreate(BaseModel):
    session_number: int | None = None
    cadence: str = "quick_check"
    players_present: str = ""
    more_of: str = ""
    less_of: str = ""
    clarify: str = ""
    notes: str = ""

    @field_validator("cadence")
    @classmethod
    def validate_cadence(cls, v: str) -> str:
        if v not in VALID_CADENCES:
            raise ValueError(f"Invalid cadence: {v}")
        return v


class FeedbackEntryPatch(BaseModel):
    session_number: int | None = None
    cadence: str | None = None
    players_present: str | None = None
    more_of: str | None = None
    less_of: str | None = None
    clarify: str | None = None
    notes: str | None = None

    @field_validator("cadence")
    @classmethod
    def validate_cadence(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CADENCES:
            raise ValueError(f"Invalid cadence: {v}")
        return v


class ActionItemCreate(BaseModel):
    item: str = ""
    owner: str = ""
    follow_up: str = ""
    status: str = "open"
    sort_order: int = 0

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_ACTION_ITEM_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class ActionItemPatch(BaseModel):
    item: str | None = None
    owner: str | None = None
    follow_up: str | None = None
    status: str | None = None
    sort_order: int | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_ACTION_ITEM_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


def _get_entry_or_404(db: DBSession, entry_id: int) -> FeedbackEntry:
    entry = db.query(FeedbackEntry).filter(FeedbackEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Feedback entry {entry_id} not found")
    return entry


def _get_action_item_or_404(db: DBSession, entry_id: int, item_id: int) -> FeedbackActionItem:
    row = (
        db.query(FeedbackActionItem)
        .filter(FeedbackActionItem.id == item_id, FeedbackActionItem.feedback_id == entry_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Action item {item_id} not found on feedback entry {entry_id}")
    return row


def _action_item_to_dict(row: FeedbackActionItem) -> dict:
    return {
        "id": row.id,
        "item": row.item,
        "owner": row.owner,
        "follow_up": row.follow_up,
        "status": row.status,
        "sort_order": row.sort_order,
    }


def _entry_to_dict(entry: FeedbackEntry) -> dict:
    return {
        "id": entry.id,
        "session_number": entry.session_number,
        "cadence": entry.cadence,
        "players_present": entry.players_present,
        "more_of": entry.more_of,
        "less_of": entry.less_of,
        "clarify": entry.clarify,
        "notes": entry.notes,
        "recorded_at": entry.recorded_at.isoformat() if entry.recorded_at else None,
        "action_items": [_action_item_to_dict(r) for r in entry.action_items],
    }


@router.get("/feedback")
def list_feedback(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(FeedbackEntry).order_by(FeedbackEntry.id.desc()).all()
    return [_entry_to_dict(r) for r in rows]


@router.get("/feedback/overdue")
def list_feedback_overdue(db: DBSession = Depends(get_db)) -> list[dict]:
    latest = db.query(func.max(Session.number)).scalar() or 0
    result = []
    for cadence, threshold in OVERDUE_THRESHOLDS.items():
        last_session = (
            db.query(func.max(FeedbackEntry.session_number))
            .filter(FeedbackEntry.cadence == cadence)
            .scalar()
        )
        sessions_since_last = latest if last_session is None else latest - last_session
        if last_session is None or sessions_since_last >= threshold:
            result.append(
                {
                    "cadence": cadence,
                    "last_session_number": last_session,
                    "sessions_since_last": sessions_since_last,
                    "threshold": threshold,
                }
            )
    return result


@router.post("/feedback", status_code=201)
def create_feedback(payload: FeedbackEntryCreate, db: DBSession = Depends(get_db)) -> dict:
    entry = FeedbackEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_to_dict(entry)


@router.get("/feedback/{entry_id}")
def get_feedback(entry_id: int, db: DBSession = Depends(get_db)) -> dict:
    return _entry_to_dict(_get_entry_or_404(db, entry_id))


@router.patch("/feedback/{entry_id}")
def patch_feedback(entry_id: int, payload: FeedbackEntryPatch, db: DBSession = Depends(get_db)) -> dict:
    entry = _get_entry_or_404(db, entry_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return _entry_to_dict(entry)


@router.delete("/feedback/{entry_id}")
def delete_feedback(entry_id: int, db: DBSession = Depends(get_db)) -> dict:
    entry = _get_entry_or_404(db, entry_id)
    db.delete(entry)
    db.commit()
    return {"deleted": True}


@router.post("/feedback/{entry_id}/action-items", status_code=201)
def create_action_item(entry_id: int, payload: ActionItemCreate, db: DBSession = Depends(get_db)) -> dict:
    _get_entry_or_404(db, entry_id)
    row = FeedbackActionItem(feedback_id=entry_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _action_item_to_dict(row)


@router.patch("/feedback/{entry_id}/action-items/{item_id}")
def patch_action_item(entry_id: int, item_id: int, payload: ActionItemPatch, db: DBSession = Depends(get_db)) -> dict:
    row = _get_action_item_or_404(db, entry_id, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _action_item_to_dict(row)


@router.delete("/feedback/{entry_id}/action-items/{item_id}")
def delete_action_item(entry_id: int, item_id: int, db: DBSession = Depends(get_db)) -> dict:
    row = _get_action_item_or_404(db, entry_id, item_id)
    db.delete(row)
    db.commit()
    return {"deleted": True}
