from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.get_db import get_db
from .schemas import IdeaIn, IdeaPatch, IdeaResponse, IdeaState
from .service import IdeaService, InvalidIdeaTransition

router = APIRouter(tags=["ideas"])
service = IdeaService()

def serialize(idea) -> dict:
    return {"id": str(idea.id), "title": idea.title, "body": idea.body, "state": idea.state, "source": idea.source, "arc_id": str(idea.arc_id) if idea.arc_id else None, "target": idea.target or {}, "visibility": idea.visibility, "created_at": idea.created_at}

def conflict(error: InvalidIdeaTransition) -> HTTPException:
    return HTTPException(409, detail={"code": "invalid_idea_transition", "message": f"Cannot move idea from {error.current_state} to {error.requested_state}.", "current_state": error.current_state, "requested_state": error.requested_state, "allowed_states": list(error.allowed_states)})

@router.get("/ideas", response_model=list[IdeaResponse])
def list_ideas(state: IdeaState | None = None, db: Session = Depends(get_db)):
    return [serialize(idea) for idea in service.list(db, state)]

@router.post("/ideas", status_code=201, response_model=IdeaResponse)
def create_idea(payload: IdeaIn, db: Session = Depends(get_db)):
    return serialize(service.create(db, payload.model_dump()))

@router.patch("/ideas/{idea_id}", response_model=IdeaResponse)
def patch_idea(idea_id: UUID, payload: IdeaPatch, db: Session = Depends(get_db)):
    try:
        idea = service.update(db, idea_id, payload.model_dump(exclude_unset=True))
    except InvalidIdeaTransition as error:
        raise conflict(error) from error
    if not idea:
        raise HTTPException(404, "Idea not found")
    return serialize(idea)

@router.post("/ideas/{idea_id}/promote", response_model=IdeaResponse)
def promote_idea(idea_id: UUID, db: Session = Depends(get_db)):
    try:
        idea = service.update(db, idea_id, {"state": "promoted"})
    except InvalidIdeaTransition as error:
        raise conflict(error) from error
    if not idea:
        raise HTTPException(404, "Idea not found")
    return serialize(idea)
