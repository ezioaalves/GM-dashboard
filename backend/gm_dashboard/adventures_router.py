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

SPINE_PRESETS: dict[str, list[str]] = {
    "six_beat": [
        "Inciting incident", "First pressure", "Complication",
        "Revelation", "Climax", "Consequence",
    ],
    "five_room": [
        "Entrance and Guardian", "Puzzle or Roleplaying Challenge", "Trick or Setback",
        "Climax, Big Battle or Conflict", "Reward, Revelation, Plot Twist",
    ],
}


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


class CastCreate(BaseModel):
    npc_id: int
    role: str = ""
    wants_now: str = ""
    hides: str = ""
    if_helped: str = ""
    if_crossed: str = ""
    sort_order: int = 0


class CastPatch(BaseModel):
    npc_id: int | None = None
    role: str | None = None
    wants_now: str | None = None
    hides: str | None = None
    if_helped: str | None = None
    if_crossed: str | None = None
    sort_order: int | None = None


class RewardCreate(BaseModel):
    name: str = ""
    type: str = ""
    who_cares: str = ""
    mechanical_note: str = ""
    future_hook: str = ""
    sort_order: int = 0


class RewardPatch(BaseModel):
    name: str | None = None
    type: str | None = None
    who_cares: str | None = None
    mechanical_note: str | None = None
    future_hook: str | None = None
    sort_order: int | None = None


class EncounterCreate(BaseModel):
    name: str = ""
    objective: str = ""
    opposition: str = ""
    terrain_constraint: str = ""
    what_changes: str = ""
    sort_order: int = 0


class EncounterPatch(BaseModel):
    name: str | None = None
    objective: str | None = None
    opposition: str | None = None
    terrain_constraint: str | None = None
    what_changes: str | None = None
    sort_order: int | None = None


class PcPressureCreate(BaseModel):
    pc_id: int
    pressure: str = ""
    growth: str = ""
    cost: str = ""
    sort_order: int = 0


class PcPressurePatch(BaseModel):
    pc_id: int | None = None
    pressure: str | None = None
    growth: str | None = None
    cost: str | None = None
    sort_order: int | None = None


class ClockLinkCreate(BaseModel):
    clock_id: str | None = None
    thread_id: str | None = None
    how_it_appears: str = ""
    advance_trigger: str = ""
    visible_impact: str = ""

    @model_validator(mode="after")
    def require_target(self) -> "ClockLinkCreate":
        if not self.clock_id and not self.thread_id:
            raise ValueError("clock_id or thread_id is required")
        return self


class ClockLinkPatch(BaseModel):
    clock_id: str | None = None
    thread_id: str | None = None
    how_it_appears: str | None = None
    advance_trigger: str | None = None
    visible_impact: str | None = None


class SpinePresetRequest(BaseModel):
    preset: str

    @field_validator("preset")
    @classmethod
    def preset_valid(cls, v: str) -> str:
        if v not in SPINE_PRESETS:
            raise ValueError(f"preset must be one of {sorted(SPINE_PRESETS)}")
        return v


def _get_adventure_or_404(db: DBSession, adventure_id: int) -> Adventure:
    adventure = db.query(Adventure).filter(Adventure.id == adventure_id).first()
    if not adventure:
        raise HTTPException(status_code=404, detail=f"Adventure {adventure_id} not found")
    return adventure


def _get_session_or_404(db: DBSession, session_id: int) -> Session:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


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


def _get_child_or_404(db: DBSession, model, row_id: int, adventure_id: int, label: str):
    row = (
        db.query(model)
        .filter(model.id == row_id, model.adventure_id == adventure_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"{label} {row_id} not found on adventure {adventure_id}")
    return row


@router.post("/adventures/{adventure_id}/cast", status_code=201)
def create_cast(adventure_id: int, payload: CastCreate, db: DBSession = Depends(get_db)) -> dict:
    _get_adventure_or_404(db, adventure_id)
    row = AdventureCast(adventure_id=adventure_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _cast_to_dict(row)


@router.patch("/adventures/{adventure_id}/cast/{cast_id}")
def patch_cast(adventure_id: int, cast_id: int, payload: CastPatch, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureCast, cast_id, adventure_id, "Cast row")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _cast_to_dict(row)


@router.delete("/adventures/{adventure_id}/cast/{cast_id}")
def delete_cast(adventure_id: int, cast_id: int, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureCast, cast_id, adventure_id, "Cast row")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/adventures/{adventure_id}/rewards", status_code=201)
def create_reward(adventure_id: int, payload: RewardCreate, db: DBSession = Depends(get_db)) -> dict:
    _get_adventure_or_404(db, adventure_id)
    row = AdventureReward(adventure_id=adventure_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _reward_to_dict(row)


@router.patch("/adventures/{adventure_id}/rewards/{reward_id}")
def patch_reward(adventure_id: int, reward_id: int, payload: RewardPatch, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureReward, reward_id, adventure_id, "Reward")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _reward_to_dict(row)


@router.delete("/adventures/{adventure_id}/rewards/{reward_id}")
def delete_reward(adventure_id: int, reward_id: int, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureReward, reward_id, adventure_id, "Reward")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/adventures/{adventure_id}/encounters", status_code=201)
def create_encounter(adventure_id: int, payload: EncounterCreate, db: DBSession = Depends(get_db)) -> dict:
    _get_adventure_or_404(db, adventure_id)
    row = AdventureEncounter(adventure_id=adventure_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _encounter_to_dict(row)


@router.patch("/adventures/{adventure_id}/encounters/{encounter_id}")
def patch_encounter(adventure_id: int, encounter_id: int, payload: EncounterPatch, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureEncounter, encounter_id, adventure_id, "Encounter")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _encounter_to_dict(row)


@router.delete("/adventures/{adventure_id}/encounters/{encounter_id}")
def delete_encounter(adventure_id: int, encounter_id: int, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureEncounter, encounter_id, adventure_id, "Encounter")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/adventures/{adventure_id}/pc-pressure", status_code=201)
def create_pc_pressure(adventure_id: int, payload: PcPressureCreate, db: DBSession = Depends(get_db)) -> dict:
    _get_adventure_or_404(db, adventure_id)
    row = AdventurePcPressure(adventure_id=adventure_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _pc_pressure_to_dict(row)


@router.patch("/adventures/{adventure_id}/pc-pressure/{row_id}")
def patch_pc_pressure(adventure_id: int, row_id: int, payload: PcPressurePatch, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventurePcPressure, row_id, adventure_id, "PC pressure row")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _pc_pressure_to_dict(row)


@router.delete("/adventures/{adventure_id}/pc-pressure/{row_id}")
def delete_pc_pressure(adventure_id: int, row_id: int, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventurePcPressure, row_id, adventure_id, "PC pressure row")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/adventures/{adventure_id}/clock-links", status_code=201)
def create_clock_link(adventure_id: int, payload: ClockLinkCreate, db: DBSession = Depends(get_db)) -> dict:
    _get_adventure_or_404(db, adventure_id)
    row = AdventureClockLink(adventure_id=adventure_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _clock_link_to_dict(row)


@router.patch("/adventures/{adventure_id}/clock-links/{link_id}")
def patch_clock_link(adventure_id: int, link_id: int, payload: ClockLinkPatch, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureClockLink, link_id, adventure_id, "Clock link")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _clock_link_to_dict(row)


@router.delete("/adventures/{adventure_id}/clock-links/{link_id}")
def delete_clock_link(adventure_id: int, link_id: int, db: DBSession = Depends(get_db)) -> dict:
    row = _get_child_or_404(db, AdventureClockLink, link_id, adventure_id, "Clock link")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/adventures/{adventure_id}/sessions/{session_id}")
def link_session(adventure_id: int, session_id: int, db: DBSession = Depends(get_db)) -> dict:
    _get_adventure_or_404(db, adventure_id)
    _get_session_or_404(db, session_id)
    existing = (
        db.query(SessionAdventure)
        .filter(
            SessionAdventure.adventure_id == adventure_id,
            SessionAdventure.session_id == session_id,
        )
        .first()
    )
    if not existing:
        db.add(SessionAdventure(adventure_id=adventure_id, session_id=session_id))
        db.commit()
    return {"linked": True}


@router.delete("/adventures/{adventure_id}/sessions/{session_id}")
def unlink_session(adventure_id: int, session_id: int, db: DBSession = Depends(get_db)) -> dict:
    _get_adventure_or_404(db, adventure_id)
    _get_session_or_404(db, session_id)
    db.query(SessionAdventure).filter(
        SessionAdventure.adventure_id == adventure_id,
        SessionAdventure.session_id == session_id,
    ).delete()
    db.commit()
    return {"unlinked": True}


@router.post("/adventures/{adventure_id}/apply-spine-preset")
def apply_spine_preset(adventure_id: int, payload: SpinePresetRequest, db: DBSession = Depends(get_db)) -> dict:
    adventure = _get_adventure_or_404(db, adventure_id)
    adventure.spine = [{"label": label, "text": ""} for label in SPINE_PRESETS[payload.preset]]
    db.commit()
    db.refresh(adventure)
    return _adventure_summary(adventure)
