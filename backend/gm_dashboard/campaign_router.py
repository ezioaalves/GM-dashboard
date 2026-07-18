"""Campaign truth and GM-controlled creative workflow endpoints.

AI-facing routes only assemble scoped context and persist proposals. They never
write vault or Foundry state implicitly.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import (
    CampaignArc, CampaignArcLink, CampaignTruth, CreativeIdea, CreativeProposal,
    ProposalAudit, Adventure, Session, Thread, LoreEntity,
)

router = APIRouter()
ARC_STATES = {"planned", "active", "completed", "archived"}
IDEA_STATES = {"captured", "triaged", "promoted", "discarded"}
TRUTH_STATES = {"provisional", "locked", "contradicted", "superseded"}
POLICIES = {"always", "scoped", "explicit_only", "never"}
PROPOSAL_STATES = {"draft", "pending_review", "accepted", "rejected", "applied", "superseded"}


class ArcIn(BaseModel):
    slug: str
    title: str
    status: str = "planned"
    summary: str = ""
    current: bool = False
    current_adventure_id: int | None = None
    current_session_id: int | None = None
    visibility: str = "gm"

    @field_validator("status")
    @classmethod
    def arc_status(cls, value: str) -> str:
        if value not in ARC_STATES:
            raise ValueError(f"status must be one of {sorted(ARC_STATES)}")
        return value


class ArcPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    summary: str | None = None
    current: bool | None = None
    current_adventure_id: int | None = None
    current_session_id: int | None = None
    visibility: str | None = None


class IdeaIn(BaseModel):
    title: str
    body: str = ""
    state: str = "captured"
    source: str = "quick_capture"
    arc_id: UUID | None = None
    target: dict[str, Any] = Field(default_factory=dict)
    visibility: str = "gm"


class IdeaPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    state: str | None = None
    arc_id: UUID | None = None
    target: dict[str, Any] | None = None
    visibility: str | None = None


class TruthIn(BaseModel):
    key: str
    statement: str
    state: str = "provisional"
    context_policy: str = "scoped"
    visibility: str = "gm"
    temporal_context: str = "current"
    source: str = "manual"
    supersedes_id: UUID | None = None


class TruthPatch(BaseModel):
    statement: str | None = None
    state: str | None = None
    context_policy: str | None = None
    visibility: str | None = None
    temporal_context: str | None = None
    supersedes_id: UUID | None = None


class ProposalIn(BaseModel):
    title: str
    task: str = ""
    target_type: str
    target_id: str = ""
    proposed_changes: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    context_checksum: str = ""
    target_surface: str = "postgres"
    state: str = "pending_review"


class DecisionIn(BaseModel):
    decision: str
    note: str = ""


class SupersedeIn(BaseModel):
    replacement_id: UUID


class ContextPacketIn(BaseModel):
    task: str
    target: str = ""
    explicit: bool = False


class ArcLinkIn(BaseModel):
    source_type: str
    source_id: str
    relation: str = "contains"


def _arc(a: CampaignArc) -> dict[str, Any]:
    return {"id": str(a.id), "slug": a.slug, "title": a.title, "status": a.status, "current": a.current,
            "summary": a.summary, "current_adventure_id": a.current_adventure_id,
            "current_session_id": a.current_session_id, "visibility": a.visibility}


def _idea(i: CreativeIdea) -> dict[str, Any]:
    return {"id": str(i.id), "title": i.title, "body": i.body, "state": i.state, "source": i.source,
            "arc_id": str(i.arc_id) if i.arc_id else None, "target": i.target or {}, "visibility": i.visibility,
            "created_at": i.created_at.isoformat() if i.created_at else None}


def _truth(t: CampaignTruth) -> dict[str, Any]:
    return {"id": str(t.id), "key": t.key, "statement": t.statement, "state": t.state,
            "context_policy": t.context_policy, "visibility": t.visibility,
            "temporal_context": t.temporal_context, "source": t.source,
            "supersedes_id": str(t.supersedes_id) if t.supersedes_id else None}


def _proposal(p: CreativeProposal) -> dict[str, Any]:
    return {"id": str(p.id), "title": p.title, "task": p.task, "target_type": p.target_type,
            "target_id": p.target_id, "state": p.state, "proposed_changes": p.proposed_changes or {},
            "context_snapshot": p.context_snapshot or {}, "context_checksum": p.context_checksum,
            "target_surface": p.target_surface, "decision": p.decision or {}}


def _set_current(db: DBSession, arc: CampaignArc) -> None:
    db.query(CampaignArc).filter(CampaignArc.id != arc.id).update({CampaignArc.current: False}, synchronize_session=False)
    arc.current = True
    arc.status = "active"


@router.get("/arcs")
def list_arcs(db: DBSession = Depends(get_db)):
    return [_arc(a) for a in db.query(CampaignArc).order_by(desc(CampaignArc.current), CampaignArc.title).all()]


@router.post("/arcs", status_code=201)
def create_arc(payload: ArcIn, db: DBSession = Depends(get_db)):
    values = payload.model_dump()
    wants_current = values.pop("current", False)
    arc = CampaignArc(**values, current=False)
    db.add(arc)
    db.flush()
    if wants_current:
        _set_current(db, arc)
    db.commit()
    return _arc(arc)


@router.patch("/arcs/{arc_id}")
def patch_arc(arc_id: UUID, payload: ArcPatch, db: DBSession = Depends(get_db)):
    arc = db.get(CampaignArc, arc_id)
    if not arc: raise HTTPException(404, "Arc not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") not in (None, *ARC_STATES): raise HTTPException(422, "Invalid arc status")
    make_current = values.pop("current", None)
    for key, value in values.items(): setattr(arc, key, value)
    if make_current: _set_current(db, arc)
    db.commit()
    return _arc(arc)


@router.post("/arcs/{arc_id}/activate")
def activate_arc(arc_id: UUID, db: DBSession = Depends(get_db)):
    arc = db.get(CampaignArc, arc_id)
    if not arc: raise HTTPException(404, "Arc not found")
    _set_current(db, arc); db.commit(); return _arc(arc)


@router.get("/arcs/{arc_id}/links")
def list_arc_links(arc_id: UUID, db: DBSession = Depends(get_db)):
    if not db.get(CampaignArc, arc_id): raise HTTPException(404, "Arc not found")
    rows = db.query(CampaignArcLink).filter(CampaignArcLink.arc_id == arc_id).order_by(CampaignArcLink.source_type, CampaignArcLink.source_id).all()
    return [{"id": str(row.id), "arc_id": str(row.arc_id), "source_type": row.source_type, "source_id": row.source_id, "relation": row.relation} for row in rows]


@router.post("/arcs/{arc_id}/links", status_code=201)
def create_arc_link(arc_id: UUID, payload: ArcLinkIn, db: DBSession = Depends(get_db)):
    if not db.get(CampaignArc, arc_id): raise HTTPException(404, "Arc not found")
    row = CampaignArcLink(arc_id=arc_id, **payload.model_dump())
    db.add(row)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(409, "Arc link already exists") from exc
    db.refresh(row)
    return {"id": str(row.id), "arc_id": str(row.arc_id), "source_type": row.source_type, "source_id": row.source_id, "relation": row.relation}


@router.get("/ideas")
def list_ideas(state: str | None = None, db: DBSession = Depends(get_db)):
    if state and state not in IDEA_STATES: raise HTTPException(422, "Invalid idea state")
    q = db.query(CreativeIdea)
    if state: q = q.filter(CreativeIdea.state == state)
    return [_idea(i) for i in q.order_by(desc(CreativeIdea.created_at)).all()]


@router.post("/ideas", status_code=201)
def create_idea(payload: IdeaIn, db: DBSession = Depends(get_db)):
    if payload.state not in IDEA_STATES: raise HTTPException(422, "Invalid idea state")
    idea = CreativeIdea(**payload.model_dump()); db.add(idea); db.commit(); db.refresh(idea); return _idea(idea)


@router.patch("/ideas/{idea_id}")
def patch_idea(idea_id: UUID, payload: IdeaPatch, db: DBSession = Depends(get_db)):
    idea = db.get(CreativeIdea, idea_id)
    if not idea: raise HTTPException(404, "Idea not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("state") and values["state"] not in IDEA_STATES: raise HTTPException(422, "Invalid idea state")
    for key, value in values.items(): setattr(idea, key, value)
    db.commit(); return _idea(idea)


@router.post("/ideas/{idea_id}/promote")
def promote_idea(idea_id: UUID, db: DBSession = Depends(get_db)):
    idea = db.get(CreativeIdea, idea_id)
    if not idea: raise HTTPException(404, "Idea not found")
    idea.state = "promoted"; db.commit(); return _idea(idea)


@router.get("/truths")
def list_truths(state: str | None = None, context_policy: str | None = None, db: DBSession = Depends(get_db)):
    q = db.query(CampaignTruth)
    if state:
        if state not in TRUTH_STATES: raise HTTPException(422, "Invalid truth state")
        q = q.filter(CampaignTruth.state == state)
    if context_policy:
        if context_policy not in POLICIES: raise HTTPException(422, "Invalid context policy")
        q = q.filter(CampaignTruth.context_policy == context_policy)
    return [_truth(t) for t in q.order_by(CampaignTruth.key).all()]


@router.post("/truths", status_code=201)
def create_truth(payload: TruthIn, db: DBSession = Depends(get_db)):
    if payload.state not in TRUTH_STATES or payload.context_policy not in POLICIES: raise HTTPException(422, "Invalid truth state or policy")
    truth = CampaignTruth(**payload.model_dump()); db.add(truth); db.commit(); db.refresh(truth); return _truth(truth)


@router.patch("/truths/{truth_id}")
def patch_truth(truth_id: UUID, payload: TruthPatch, db: DBSession = Depends(get_db)):
    truth = db.get(CampaignTruth, truth_id)
    if not truth: raise HTTPException(404, "Truth not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("state") and values["state"] not in TRUTH_STATES: raise HTTPException(422, "Invalid truth state")
    if values.get("context_policy") and values["context_policy"] not in POLICIES: raise HTTPException(422, "Invalid context policy")
    for key, value in values.items(): setattr(truth, key, value)
    db.commit(); return _truth(truth)


@router.post("/truths/{truth_id}/supersede")
def supersede_truth(truth_id: UUID, payload: SupersedeIn, db: DBSession = Depends(get_db)):
    old, new = db.get(CampaignTruth, truth_id), db.get(CampaignTruth, payload.replacement_id)
    if not old or not new: raise HTTPException(404, "Truth not found")
    old.state = "superseded"; new.supersedes_id = old.id; db.commit(); return {"superseded": str(old.id), "replacement": str(new.id)}


@router.post("/context-packets")
def context_packet(payload: ContextPacketIn | None = None, task: str = "", target: str = "", explicit: bool = False, db: DBSession = Depends(get_db)):
    if payload is not None:
        task, target, explicit = payload.task, payload.target, payload.explicit
    arc = db.query(CampaignArc).filter(CampaignArc.current.is_(True)).first()
    truths = db.query(CampaignTruth).filter(CampaignTruth.state.notin_(["contradicted", "superseded"])).all()
    selected = [t for t in truths if t.context_policy == "always" or (t.context_policy == "scoped" and (not target or target.lower() in (t.statement + t.key).lower())) or (explicit and t.context_policy == "explicit_only")]
    adventures = db.query(Adventure).filter(Adventure.current_arc == arc.title).all() if arc else []
    sessions = db.query(Session).filter(Session.status.in_(["planned", "ready"])).order_by(Session.number).limit(3).all()
    packet = {"task": task, "target": target, "arc": _arc(arc) if arc else None,
              "adventures": [{"id": a.id, "title": a.title, "status": a.status} for a in adventures],
              "sessions": [{"number": s.number, "name": s.name, "status": s.status} for s in sessions],
              "truths": [_truth(t) for t in selected], "policy": {"explicit": explicit}}
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":"))
    packet["checksum"] = hashlib.sha256(encoded.encode()).hexdigest()
    return packet


@router.get("/creative-proposals")
def list_proposals(state: str | None = None, db: DBSession = Depends(get_db)):
    q = db.query(CreativeProposal)
    if state:
        if state not in PROPOSAL_STATES: raise HTTPException(422, "Invalid proposal state")
        q = q.filter(CreativeProposal.state == state)
    return [_proposal(p) for p in q.order_by(desc(CreativeProposal.created_at)).all()]


@router.post("/creative-proposals", status_code=201)
def create_proposal(payload: ProposalIn, db: DBSession = Depends(get_db)):
    if payload.state not in PROPOSAL_STATES: raise HTTPException(422, "Invalid proposal state")
    checksum = payload.context_checksum or hashlib.sha256(json.dumps(payload.context_snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    proposal = CreativeProposal(**payload.model_dump(exclude={"context_checksum"}), context_checksum=checksum)
    db.add(proposal); db.commit(); db.refresh(proposal); return _proposal(proposal)


@router.post("/creative-proposals/{proposal_id}/decision")
def decide_proposal(proposal_id: UUID, payload: DecisionIn, db: DBSession = Depends(get_db)):
    proposal = db.get(CreativeProposal, proposal_id)
    if not proposal: raise HTTPException(404, "Proposal not found")
    if payload.decision not in {"accept", "reject", "supersede"}: raise HTTPException(422, "Invalid decision")
    proposal.state = {"accept": "accepted", "reject": "rejected", "supersede": "superseded"}[payload.decision]
    proposal.decision = {"decision": payload.decision, "note": payload.note}
    db.add(ProposalAudit(proposal_id=proposal.id, action=payload.decision, result=proposal.decision))
    db.commit(); return _proposal(proposal)


@router.post("/creative-proposals/{proposal_id}/apply")
def apply_proposal(proposal_id: UUID, db: DBSession = Depends(get_db)):
    proposal = db.get(CreativeProposal, proposal_id)
    if not proposal: raise HTTPException(404, "Proposal not found")
    if proposal.state != "accepted": raise HTTPException(409, "Proposal must be accepted before applying")
    changes = proposal.proposed_changes or {}
    result: dict[str, Any]
    if proposal.target_surface in {"vault", "foundry_test", "foundry_prod"}:
        # Prose/runtime changes always enter the normal review gate.
        from .db.models import SyncReview
        review = SyncReview(review_type="creative_proposal", source_surface="postgres", target_surface=proposal.target_surface,
                            target_type=proposal.target_type, target_id=proposal.target_id, proposed_changes=changes)
        db.add(review); db.flush(); result = {"review_id": str(review.id), "state": "review_required"}
    elif proposal.target_type == "truth":
        truth = db.get(CampaignTruth, UUID(proposal.target_id))
        if not truth: raise HTTPException(404, "Proposal target not found")
        for key, value in changes.items():
            if key in {"statement", "state", "context_policy", "visibility", "temporal_context"}: setattr(truth, key, value)
        result = {"truth_id": str(truth.id), "state": "applied"}
    else:
        result = {"state": "applied", "target_type": proposal.target_type, "target_id": proposal.target_id}
    audit = ProposalAudit(proposal_id=proposal.id, action="apply", result=result)
    db.add(audit); db.flush(); proposal.applied_audit_id = audit.id; proposal.state = "applied"; db.commit()
    return {**_proposal(proposal), "result": result, "audit_id": str(audit.id)}
