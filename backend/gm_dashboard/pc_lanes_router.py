from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import PC, PcLane, Thread

router = APIRouter()

VALID_LANE_STATUSES = {"active", "stalled", "resolved", "shelved"}


class PcLaneUpsert(BaseModel):
    goal: str = ""
    status: str = "active"
    pressure: str = ""
    notes: str = ""
    last_touched_session: int | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_LANE_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


def _get_pc_or_404(db: DBSession, slug: str) -> PC:
    pc = db.query(PC).filter(PC.slug == slug).first()
    if not pc:
        raise HTTPException(status_code=404, detail=f"PC '{slug}' not found")
    return pc


def _owned_threads(db: DBSession, pc_name: str) -> list[dict]:
    """Best-effort name match against threads.factions (free-text, not FK'd to pcs)."""
    rows = db.query(Thread).filter(Thread.factions.any(pc_name)).order_by(Thread.title).all()
    return [{"id": t.id, "title": t.title, "status": t.status} for t in rows]


def _lane_to_dict(pc: PC, lane: PcLane | None, owned_threads: list[dict]) -> dict:
    return {
        "pc_id": pc.id,
        "slug": pc.slug,
        "name": pc.name,
        "player": pc.player,
        "goal": lane.goal if lane else "",
        "status": lane.status if lane else "active",
        "pressure": lane.pressure if lane else "",
        "notes": lane.notes if lane else "",
        "last_touched_session": lane.last_touched_session if lane else None,
        "has_lane": lane is not None,
        "owned_threads": owned_threads,
    }


@router.get("/pc-lanes")
def list_pc_lanes(db: DBSession = Depends(get_db)) -> list[dict]:
    """List every PC with its lane (if any) and read-only owned threads."""
    pcs = db.query(PC).order_by(PC.name).all()
    lanes_by_pc_id = {lane.pc_id: lane for lane in db.query(PcLane).all()}
    return [
        _lane_to_dict(pc, lanes_by_pc_id.get(pc.id), _owned_threads(db, pc.name))
        for pc in pcs
    ]


@router.get("/pcs/{slug}/lane")
def get_pc_lane(slug: str, db: DBSession = Depends(get_db)) -> dict:
    pc = _get_pc_or_404(db, slug)
    lane = db.query(PcLane).filter(PcLane.pc_id == pc.id).first()
    if not lane:
        raise HTTPException(status_code=404, detail=f"No lane exists yet for PC '{slug}'")
    return _lane_to_dict(pc, lane, _owned_threads(db, pc.name))


@router.put("/pcs/{slug}/lane")
def upsert_pc_lane(slug: str, payload: PcLaneUpsert, db: DBSession = Depends(get_db)) -> dict:
    pc = _get_pc_or_404(db, slug)
    lane = db.query(PcLane).filter(PcLane.pc_id == pc.id).first()
    if lane is None:
        lane = PcLane(pc_id=pc.id, **payload.model_dump())
        db.add(lane)
    else:
        for field, value in payload.model_dump().items():
            setattr(lane, field, value)
    db.commit()
    db.refresh(lane)
    return _lane_to_dict(pc, lane, _owned_threads(db, pc.name))
