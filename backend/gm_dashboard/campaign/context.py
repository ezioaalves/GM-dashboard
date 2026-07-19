from __future__ import annotations
import hashlib
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db.get_db import get_db
from ..db.models import Adventure, CampaignArc, CampaignTruth, Session
from .schemas import ContextPacketIn
from .serializers import arc_response, truth_response

router = APIRouter(tags=["context"])

@router.post("/context-packets")
def context_packet(payload: ContextPacketIn | None = None, task: str = "", target: str = "", explicit: bool = False, db: Session = Depends(get_db)):
    if payload is not None: task, target, explicit = payload.task, payload.target, payload.explicit
    arc = db.query(CampaignArc).filter(CampaignArc.current.is_(True)).first()
    truths = db.query(CampaignTruth).filter(CampaignTruth.state.notin_(["contradicted", "superseded"])).all()
    selected = [truth for truth in truths if truth.context_policy == "always" or (truth.context_policy == "scoped" and (not target or target.lower() in (truth.statement + truth.key).lower())) or (explicit and truth.context_policy == "explicit_only")]
    adventures = db.query(Adventure).filter(Adventure.current_arc == arc.title).all() if arc else []
    sessions = db.query(Session).filter(Session.status.in_(["planned", "ready"])).order_by(Session.number).limit(3).all()
    packet = {"task": task, "target": target, "arc": arc_response(arc) if arc else None, "adventures": [{"id": adventure.id, "title": adventure.title, "status": adventure.status} for adventure in adventures], "sessions": [{"number": session.number, "name": session.name, "status": session.status} for session in sessions], "truths": [truth_response(truth) for truth in selected], "policy": {"explicit": explicit}}
    packet["checksum"] = hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return packet
