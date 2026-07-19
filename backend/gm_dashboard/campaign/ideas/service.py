from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from ...db.models import CreativeIdea
from .repository import IdeaRepository

IDEA_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "captured": ("captured", "triaged", "discarded"),
    "triaged": ("triaged", "captured", "promoted", "discarded"),
    "promoted": ("promoted", "triaged"),
    "discarded": ("discarded", "captured"),
}

@dataclass
class InvalidIdeaTransition(Exception):
    current_state: str
    requested_state: str
    allowed_states: tuple[str, ...]

class IdeaService:
    def __init__(self, repository: IdeaRepository | None = None):
        self.repository = repository or IdeaRepository()
    def list(self, db: Session, state: str | None = None) -> list[CreativeIdea]:
        return self.repository.list(db, state)
    def create(self, db: Session, values: dict[str, Any]) -> CreativeIdea:
        idea = self.repository.add(db, CreativeIdea(**values))
        db.commit(); db.refresh(idea)
        return idea
    def update(self, db: Session, idea_id: UUID, values: dict[str, Any]) -> CreativeIdea | None:
        idea = self.repository.get(db, idea_id)
        if not idea:
            return None
        requested = values.get("state")
        if requested and requested not in IDEA_TRANSITIONS[idea.state]:
            raise InvalidIdeaTransition(idea.state, requested, IDEA_TRANSITIONS[idea.state])
        for key, value in values.items():
            setattr(idea, key, value)
        if values:
            db.commit(); db.refresh(idea)
        return idea
