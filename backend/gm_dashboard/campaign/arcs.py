from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session
from ..db.get_db import get_db
from ..db.models import CampaignArc, CampaignArcLink
from .schemas import ArcIn, ArcLinkIn, ArcLinkResponse, ArcPatch, ArcResponse
from .serializers import arc_response

router = APIRouter(tags=["arcs"])

def set_current(db: Session, arc: CampaignArc) -> None:
    db.query(CampaignArc).filter(CampaignArc.id != arc.id).update({CampaignArc.current: False}, synchronize_session=False)
    arc.current = True
    arc.status = "active"

@router.get("/arcs", response_model=list[ArcResponse])
def list_arcs(db: Session = Depends(get_db)):
    return [arc_response(arc) for arc in db.query(CampaignArc).order_by(desc(CampaignArc.current), CampaignArc.title).all()]

@router.post("/arcs", status_code=201, response_model=ArcResponse)
def create_arc(payload: ArcIn, db: Session = Depends(get_db)):
    values = payload.model_dump(); wants_current = values.pop("current", False)
    arc = CampaignArc(**values, current=False); db.add(arc); db.flush()
    if wants_current: set_current(db, arc)
    db.commit(); db.refresh(arc)
    return arc_response(arc)

@router.patch("/arcs/{arc_id}", response_model=ArcResponse)
def patch_arc(arc_id: UUID, payload: ArcPatch, db: Session = Depends(get_db)):
    arc = db.get(CampaignArc, arc_id)
    if not arc: raise HTTPException(404, "Arc not found")
    values = payload.model_dump(exclude_unset=True); make_current = values.pop("current", None)
    for key, value in values.items(): setattr(arc, key, value)
    if make_current: set_current(db, arc)
    db.commit(); db.refresh(arc)
    return arc_response(arc)

@router.post("/arcs/{arc_id}/activate", response_model=ArcResponse)
def activate_arc(arc_id: UUID, db: Session = Depends(get_db)):
    arc = db.get(CampaignArc, arc_id)
    if not arc: raise HTTPException(404, "Arc not found")
    set_current(db, arc); db.commit(); db.refresh(arc)
    return arc_response(arc)

@router.get("/arcs/{arc_id}/links", response_model=list[ArcLinkResponse])
def list_arc_links(arc_id: UUID, db: Session = Depends(get_db)):
    if not db.get(CampaignArc, arc_id): raise HTTPException(404, "Arc not found")
    rows = db.query(CampaignArcLink).filter(CampaignArcLink.arc_id == arc_id).order_by(CampaignArcLink.source_type, CampaignArcLink.source_id).all()
    return [{"id": str(row.id), "arc_id": str(row.arc_id), "source_type": row.source_type, "source_id": row.source_id, "relation": row.relation} for row in rows]

@router.post("/arcs/{arc_id}/links", status_code=201, response_model=ArcLinkResponse)
def create_arc_link(arc_id: UUID, payload: ArcLinkIn, db: Session = Depends(get_db)):
    if not db.get(CampaignArc, arc_id): raise HTTPException(404, "Arc not found")
    row = CampaignArcLink(arc_id=arc_id, **payload.model_dump()); db.add(row)
    try: db.commit()
    except Exception as error:
        db.rollback(); raise HTTPException(409, "Arc link already exists") from error
    db.refresh(row)
    return {"id": str(row.id), "arc_id": str(row.arc_id), "source_type": row.source_type, "source_id": row.source_id, "relation": row.relation}
