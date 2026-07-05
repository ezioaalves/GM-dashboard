from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import (
    Adventure,
    AdventureCast,
    AdventureClockLink,
    AdventureEncounter,
    AdventurePcPressure,
    AdventureReward,
    Session,
    SessionAdventure,
)
from .system_enums import FRESHNESS_STATES, REVIEW_STATUSES, VISIBILITIES

router = APIRouter()

VALID_ADVENTURE_STATUSES = {"draft", "ready", "played", "archived"}


class AdventureCreate(BaseModel):
    title: str = ""
    status: str = "draft"
    current_arc: str = ""
    pitch: str = ""
    mode: str = ""
    tone_rule: str = ""
    safety_flags: str = ""
    feel_target: str = ""
    feel_avoid: str = ""
    stakes: dict[str, Any] = Field(default_factory=dict)
    location: dict[str, Any] = Field(default_factory=dict)
    spine: list[dict[str, Any]] = Field(default_factory=list)
    clue_map: dict[str, Any] = Field(default_factory=dict)
    foundry_needs: dict[str, Any] = Field(default_factory=dict)
    rules_notes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_ADVENTURE_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class AdventurePatch(BaseModel):
    title: str | None = None
    status: str | None = None
    current_arc: str | None = None
    pitch: str | None = None
    mode: str | None = None
    tone_rule: str | None = None
    safety_flags: str | None = None
    feel_target: str | None = None
    feel_avoid: str | None = None
    stakes: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    spine: list[dict[str, Any]] | None = None
    clue_map: dict[str, Any] | None = None
    foundry_needs: dict[str, Any] | None = None
    rules_notes: dict[str, Any] | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    review_status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_ADVENTURE_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v

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


def _get_adventure_or_404(db: DBSession, adventure_id: int) -> Adventure:
    adventure = db.query(Adventure).filter(Adventure.id == adventure_id).first()
    if not adventure:
        raise HTTPException(status_code=404, detail=f"Adventure {adventure_id} not found")
    return adventure


def _adventure_summary(adventure: Adventure, session_count: int = 0) -> dict:
    return {
        "id": adventure.id,
        "graph_endpoint_id": adventure.graph_endpoint_id or f"adventure:{adventure.id}",
        "title": adventure.title,
        "status": adventure.status,
        "current_arc": adventure.current_arc,
        "pitch": adventure.pitch,
        "mode": adventure.mode,
        "tone_rule": adventure.tone_rule,
        "safety_flags": adventure.safety_flags,
        "feel_target": adventure.feel_target,
        "feel_avoid": adventure.feel_avoid,
        "stakes": adventure.stakes or {},
        "location": adventure.location or {},
        "spine": adventure.spine or [],
        "clue_map": adventure.clue_map or {},
        "foundry_needs": adventure.foundry_needs or {},
        "rules_notes": adventure.rules_notes or {},
        "visibility": adventure.visibility or "gm",
        "freshness_state": adventure.freshness_state or "unknown",
        "review_status": adventure.review_status or "accepted",
        "session_count": session_count,
    }


def _pc_pressure_to_dict(row: AdventurePcPressure) -> dict:
    return {
        "id": row.id, "pc_id": row.pc_id, "pressure": row.pressure,
        "growth": row.growth, "cost": row.cost, "sort_order": row.sort_order,
    }


def _reward_to_dict(row: AdventureReward) -> dict:
    return {
        "id": row.id, "name": row.name, "type": row.type, "who_cares": row.who_cares,
        "mechanical_note": row.mechanical_note, "future_hook": row.future_hook,
        "sort_order": row.sort_order,
    }


def _clock_link_to_dict(row: AdventureClockLink) -> dict:
    return {
        "id": row.id,
        "clock_id": str(row.clock_id) if row.clock_id else None,
        "thread_id": row.thread_id,
        "how_it_appears": row.how_it_appears,
        "advance_trigger": row.advance_trigger,
        "visible_impact": row.visible_impact,
    }


def _encounter_to_dict(row: AdventureEncounter) -> dict:
    return {
        "id": row.id, "name": row.name, "objective": row.objective,
        "opposition": row.opposition, "terrain_constraint": row.terrain_constraint,
        "what_changes": row.what_changes, "sort_order": row.sort_order,
    }


def _cast_to_dict(row: AdventureCast) -> dict:
    return {
        "id": row.id, "npc_id": row.npc_id, "role": row.role,
        "wants_now": row.wants_now, "hides": row.hides,
        "if_helped": row.if_helped, "if_crossed": row.if_crossed,
        "sort_order": row.sort_order,
    }


def _adventure_detail(db: DBSession, adventure: Adventure) -> dict:
    linked_sessions = (
        db.query(Session)
        .join(SessionAdventure, SessionAdventure.session_id == Session.id)
        .filter(SessionAdventure.adventure_id == adventure.id)
        .order_by(Session.number.asc())
        .all()
    )
    detail = _adventure_summary(adventure, session_count=len(linked_sessions))
    detail["pc_pressure"] = [_pc_pressure_to_dict(r) for r in adventure.pc_pressure]
    detail["rewards"] = [_reward_to_dict(r) for r in adventure.rewards]
    detail["clock_links"] = [_clock_link_to_dict(r) for r in adventure.clock_links]
    detail["encounters"] = [_encounter_to_dict(r) for r in adventure.encounters]
    detail["cast"] = [_cast_to_dict(r) for r in adventure.cast]
    detail["sessions"] = [{"id": s.id, "title": s.name or f"Session {s.number}"} for s in linked_sessions]
    return detail


@router.get("/adventures")
def list_adventures(status: str | None = None, db: DBSession = Depends(get_db)) -> list[dict]:
    """
    List all adventures, optionally filtered by status.

    Query params:
      status: (optional) Filter to adventures with this status
    """
    if status is not None and status not in VALID_ADVENTURE_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}")

    query = db.query(Adventure)
    if status is not None:
        query = query.filter(Adventure.status == status)
    adventures = query.order_by(Adventure.id.desc()).all()
    result = []
    for adventure in adventures:
        session_count = (
            db.query(SessionAdventure)
            .filter(SessionAdventure.adventure_id == adventure.id)
            .count()
        )
        result.append(_adventure_summary(adventure, session_count))
    return result


@router.post("/adventures", status_code=201)
def create_adventure(payload: AdventureCreate, db: DBSession = Depends(get_db)) -> dict:
    adventure = Adventure(**payload.model_dump())
    db.add(adventure)
    db.commit()
    db.refresh(adventure)
    return _adventure_summary(adventure)


@router.get("/adventures/{adventure_id}")
def get_adventure(adventure_id: int, db: DBSession = Depends(get_db)) -> dict:
    adventure = _get_adventure_or_404(db, adventure_id)
    return _adventure_detail(db, adventure)


@router.patch("/adventures/{adventure_id}")
def patch_adventure(adventure_id: int, payload: AdventurePatch, db: DBSession = Depends(get_db)) -> dict:
    adventure = _get_adventure_or_404(db, adventure_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(adventure, field, value)
    db.commit()
    db.refresh(adventure)
    return _adventure_detail(db, adventure)


@router.delete("/adventures/{adventure_id}")
def delete_adventure(adventure_id: int, db: DBSession = Depends(get_db)) -> dict:
    adventure = _get_adventure_or_404(db, adventure_id)
    db.delete(adventure)
    db.commit()
    return {"deleted": True}
