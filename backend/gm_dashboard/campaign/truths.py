from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.get_db import get_db
from ..db.models import CampaignTruth
from .schemas import ContextPolicy, SupersedeIn, TruthIn, TruthPatch, TruthResponse, TruthState
from .serializers import truth_response

router = APIRouter(tags=["truths"])

@router.get("/truths", response_model=list[TruthResponse])
def list_truths(state: TruthState | None = None, context_policy: ContextPolicy | None = None, db: Session = Depends(get_db)):
    query = db.query(CampaignTruth)
    if state: query = query.filter(CampaignTruth.state == state)
    if context_policy: query = query.filter(CampaignTruth.context_policy == context_policy)
    return [truth_response(truth) for truth in query.order_by(CampaignTruth.key).all()]

@router.post("/truths", status_code=201, response_model=TruthResponse)
def create_truth(payload: TruthIn, db: Session = Depends(get_db)):
    truth = CampaignTruth(**payload.model_dump()); db.add(truth); db.commit(); db.refresh(truth)
    return truth_response(truth)

@router.patch("/truths/{truth_id}", response_model=TruthResponse)
def patch_truth(truth_id: UUID, payload: TruthPatch, db: Session = Depends(get_db)):
    truth = db.get(CampaignTruth, truth_id)
    if not truth: raise HTTPException(404, "Truth not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(truth, key, value)
    db.commit(); db.refresh(truth)
    return truth_response(truth)

@router.post("/truths/{truth_id}/supersede")
def supersede_truth(truth_id: UUID, payload: SupersedeIn, db: Session = Depends(get_db)):
    old, new = db.get(CampaignTruth, truth_id), db.get(CampaignTruth, payload.replacement_id)
    if not old or not new: raise HTTPException(404, "Truth not found")
    old.state = "superseded"; new.supersedes_id = old.id; db.commit()
    return {"superseded": str(old.id), "replacement": str(new.id)}
