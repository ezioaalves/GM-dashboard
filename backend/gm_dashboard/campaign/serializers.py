from __future__ import annotations
from typing import Any
from ..db.models import CampaignArc, CampaignTruth, CreativeProposal

def arc_response(arc: CampaignArc) -> dict[str, Any]:
    return {"id": str(arc.id), "slug": arc.slug, "title": arc.title, "status": arc.status, "current": arc.current, "summary": arc.summary, "current_adventure_id": arc.current_adventure_id, "current_session_id": arc.current_session_id, "visibility": arc.visibility}

def truth_response(truth: CampaignTruth) -> dict[str, Any]:
    return {"id": str(truth.id), "key": truth.key, "statement": truth.statement, "state": truth.state, "context_policy": truth.context_policy, "visibility": truth.visibility, "temporal_context": truth.temporal_context, "source": truth.source, "supersedes_id": str(truth.supersedes_id) if truth.supersedes_id else None}

def proposal_response(proposal: CreativeProposal) -> dict[str, Any]:
    return {"id": str(proposal.id), "title": proposal.title, "task": proposal.task, "target_type": proposal.target_type, "target_id": proposal.target_id, "state": proposal.state, "proposed_changes": proposal.proposed_changes or {}, "context_snapshot": proposal.context_snapshot or {}, "context_checksum": proposal.context_checksum, "target_surface": proposal.target_surface, "decision": proposal.decision or {}}
