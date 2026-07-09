from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import Risk, Session

router = APIRouter()

VALID_LIKELIHOODS = {"low", "medium", "high"}
VALID_RISK_STATUSES = {"open", "mitigated", "triggered", "closed"}
DEFAULT_STALE_THRESHOLD = 3


class RiskCreate(BaseModel):
    title: str = ""
    description: str = ""
    likelihood: str = "medium"
    mitigation: str = ""
    contingency: str = ""
    status: str = "open"
    related_thread_id: str | None = None
    related_pc_id: int | None = None

    @field_validator("likelihood")
    @classmethod
    def validate_likelihood(cls, v: str) -> str:
        if v not in VALID_LIKELIHOODS:
            raise ValueError(f"Invalid likelihood: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_RISK_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class RiskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    likelihood: str | None = None
    mitigation: str | None = None
    contingency: str | None = None
    status: str | None = None
    related_thread_id: str | None = None
    related_pc_id: int | None = None

    @field_validator("likelihood")
    @classmethod
    def validate_likelihood(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_LIKELIHOODS:
            raise ValueError(f"Invalid likelihood: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_RISK_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class MarkReviewedRequest(BaseModel):
    session_number: int


def _get_risk_or_404(db: DBSession, risk_id: int) -> Risk:
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail=f"Risk {risk_id} not found")
    return risk


def _risk_to_dict(risk: Risk) -> dict:
    return {
        "id": risk.id,
        "title": risk.title,
        "description": risk.description,
        "likelihood": risk.likelihood,
        "mitigation": risk.mitigation,
        "contingency": risk.contingency,
        "status": risk.status,
        "related_thread_id": risk.related_thread_id,
        "related_pc_id": risk.related_pc_id,
        "last_reviewed_session": risk.last_reviewed_session,
    }


def _latest_session_number(db: DBSession) -> int:
    return db.query(func.max(Session.number)).scalar() or 0


@router.get("/risks")
def list_risks(
    status: str | None = None, likelihood: str | None = None, db: DBSession = Depends(get_db)
) -> list[dict]:
    if status is not None and status not in VALID_RISK_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    if likelihood is not None and likelihood not in VALID_LIKELIHOODS:
        raise HTTPException(status_code=422, detail=f"Invalid likelihood: {likelihood}")

    query = db.query(Risk)
    if status is not None:
        query = query.filter(Risk.status == status)
    if likelihood is not None:
        query = query.filter(Risk.likelihood == likelihood)
    rows = query.order_by(Risk.id.desc()).all()
    return [_risk_to_dict(r) for r in rows]


@router.get("/risks/stale")
def list_stale_risks(threshold: int = DEFAULT_STALE_THRESHOLD, db: DBSession = Depends(get_db)) -> list[dict]:
    latest = _latest_session_number(db)
    rows = db.query(Risk).filter(Risk.status == "open").order_by(Risk.id.desc()).all()
    return [
        _risk_to_dict(r)
        for r in rows
        if r.last_reviewed_session is None or (latest - r.last_reviewed_session) >= threshold
    ]


@router.post("/risks", status_code=201)
def create_risk(payload: RiskCreate, db: DBSession = Depends(get_db)) -> dict:
    risk = Risk(**payload.model_dump())
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return _risk_to_dict(risk)


@router.get("/risks/{risk_id}")
def get_risk(risk_id: int, db: DBSession = Depends(get_db)) -> dict:
    return _risk_to_dict(_get_risk_or_404(db, risk_id))


@router.patch("/risks/{risk_id}")
def patch_risk(risk_id: int, payload: RiskPatch, db: DBSession = Depends(get_db)) -> dict:
    risk = _get_risk_or_404(db, risk_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(risk, field, value)
    db.commit()
    db.refresh(risk)
    return _risk_to_dict(risk)


@router.delete("/risks/{risk_id}")
def delete_risk(risk_id: int, db: DBSession = Depends(get_db)) -> dict:
    risk = _get_risk_or_404(db, risk_id)
    db.delete(risk)
    db.commit()
    return {"deleted": True}


@router.post("/risks/{risk_id}/mark-reviewed")
def mark_risk_reviewed(risk_id: int, payload: MarkReviewedRequest, db: DBSession = Depends(get_db)) -> dict:
    risk = _get_risk_or_404(db, risk_id)
    risk.last_reviewed_session = payload.session_number
    db.commit()
    db.refresh(risk)
    return _risk_to_dict(risk)
