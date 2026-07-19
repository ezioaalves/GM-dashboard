from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.get_db import get_db
from ..db.models import CampaignTruth, CreativeProposal, ProposalAudit, SyncReview
from .schemas import DecisionIn, ProposalIn, ProposalResponse, ProposalState
from .serializers import proposal_response

router = APIRouter(tags=["creative-proposals"])


class ProposalApplyStrategy(Protocol):
    def matches(self, proposal: CreativeProposal) -> bool: ...
    def apply(self, db: Session, proposal: CreativeProposal) -> dict: ...


class ReviewGatedSurfaceStrategy:
    surfaces = {"vault", "foundry_test", "foundry_prod"}

    def matches(self, proposal: CreativeProposal) -> bool:
        return proposal.target_surface in self.surfaces

    def apply(self, db: Session, proposal: CreativeProposal) -> dict:
        review = SyncReview(
            review_type="creative_proposal", source_surface="postgres",
            target_surface=proposal.target_surface, target_type=proposal.target_type,
            target_id=proposal.target_id, proposed_changes=proposal.proposed_changes or {},
        )
        db.add(review); db.flush()
        # Review creation is not an execution; the accepted review apply path
        # owns the later sync_job.
        return {"review_id": str(review.id), "state": "review_required"}


class TruthUpdateStrategy:
    allowed_fields = {"statement", "state", "context_policy", "visibility", "temporal_context"}

    def matches(self, proposal: CreativeProposal) -> bool:
        return proposal.target_type == "truth"

    def apply(self, db: Session, proposal: CreativeProposal) -> dict:
        try:
            truth_id = UUID(proposal.target_id)
        except ValueError as error:
            raise HTTPException(422, "Proposal truth target must be a UUID") from error
        truth = db.get(CampaignTruth, truth_id)
        if not truth: raise HTTPException(404, "Proposal target not found")
        for key, value in (proposal.proposed_changes or {}).items():
            if key in self.allowed_fields: setattr(truth, key, value)
        return {"truth_id": str(truth.id), "state": "applied"}


class FallbackStrategy:
    def matches(self, proposal: CreativeProposal) -> bool:
        return True

    def apply(self, db: Session, proposal: CreativeProposal) -> dict:
        return {"state": "applied", "target_type": proposal.target_type, "target_id": proposal.target_id}


STRATEGIES: tuple[ProposalApplyStrategy, ...] = (
    ReviewGatedSurfaceStrategy(), TruthUpdateStrategy(), FallbackStrategy(),
)


def apply_strategy(db: Session, proposal: CreativeProposal) -> dict:
    for strategy in STRATEGIES:
        if strategy.matches(proposal): return strategy.apply(db, proposal)
    raise AssertionError("fallback proposal strategy is required")


@router.get("/creative-proposals", response_model=list[ProposalResponse])
def list_proposals(state: ProposalState | None = None, db: Session = Depends(get_db)):
    query = db.query(CreativeProposal)
    if state: query = query.filter(CreativeProposal.state == state)
    return [proposal_response(proposal) for proposal in query.order_by(CreativeProposal.created_at.desc()).all()]


@router.post("/creative-proposals", status_code=201, response_model=ProposalResponse)
def create_proposal(payload: ProposalIn, db: Session = Depends(get_db)):
    values = payload.model_dump()
    checksum = values.pop("context_checksum") or hashlib.sha256(json.dumps(values["context_snapshot"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    proposal = CreativeProposal(**values, context_checksum=checksum)
    db.add(proposal); db.commit(); db.refresh(proposal)
    return proposal_response(proposal)


@router.post("/creative-proposals/{proposal_id}/decision", response_model=ProposalResponse)
def decide_proposal(proposal_id: UUID, payload: DecisionIn, db: Session = Depends(get_db)):
    proposal = db.get(CreativeProposal, proposal_id)
    if not proposal: raise HTTPException(404, "Proposal not found")
    proposal.state = {"accept": "accepted", "reject": "rejected", "supersede": "superseded"}[payload.decision]
    proposal.decision = {"decision": payload.decision, "note": payload.note}
    db.add(ProposalAudit(proposal_id=proposal.id, action=payload.decision, result=proposal.decision))
    db.commit(); db.refresh(proposal)
    return proposal_response(proposal)


@router.post("/creative-proposals/{proposal_id}/apply")
def apply_proposal(proposal_id: UUID, db: Session = Depends(get_db)):
    proposal = db.get(CreativeProposal, proposal_id)
    if not proposal: raise HTTPException(404, "Proposal not found")
    if proposal.state != "accepted": raise HTTPException(409, "Proposal must be accepted before applying")
    result = apply_strategy(db, proposal)
    audit = ProposalAudit(proposal_id=proposal.id, action="apply", result=result)
    db.add(audit); db.flush()
    proposal.applied_audit_id = audit.id; proposal.state = "applied"
    db.commit(); db.refresh(proposal)
    return {**proposal_response(proposal), "result": result, "audit_id": str(audit.id)}
