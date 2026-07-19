from __future__ import annotations
from uuid import UUID
from sqlalchemy import desc
from sqlalchemy.orm import Session
from ...db.models import CreativeIdea

class IdeaRepository:
    def get(self, db: Session, idea_id: UUID) -> CreativeIdea | None:
        return db.get(CreativeIdea, idea_id)
    def list(self, db: Session, state: str | None = None) -> list[CreativeIdea]:
        query = db.query(CreativeIdea)
        if state:
            query = query.filter(CreativeIdea.state == state)
        return query.order_by(desc(CreativeIdea.created_at), desc(CreativeIdea.id)).all()
    def add(self, db: Session, idea: CreativeIdea) -> CreativeIdea:
        db.add(idea)
        return idea
