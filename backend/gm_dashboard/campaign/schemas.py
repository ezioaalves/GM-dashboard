from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ArcState = Literal["planned", "active", "completed", "archived"]
TruthState = Literal["provisional", "locked", "contradicted", "superseded"]
ContextPolicy = Literal["always", "scoped", "explicit_only", "never"]
ProposalState = Literal["draft", "pending_review", "accepted", "rejected", "applied", "superseded"]

class ArcIn(BaseModel):
    slug: str
    title: str
    status: ArcState = "planned"
    summary: str = ""
    current: bool = False
    current_adventure_id: int | None = None
    current_session_id: int | None = None
    visibility: str = "gm"

class ArcPatch(BaseModel):
    title: str | None = None
    status: ArcState | None = None
    summary: str | None = None
    current: bool | None = None
    current_adventure_id: int | None = None
    current_session_id: int | None = None
    visibility: str | None = None

class ArcResponse(BaseModel):
    id: str
    slug: str
    title: str
    status: ArcState
    current: bool
    summary: str
    current_adventure_id: int | None
    current_session_id: int | None
    visibility: str

class ArcLinkIn(BaseModel):
    source_type: str
    source_id: str
    relation: str = "contains"

class ArcLinkResponse(BaseModel):
    id: str
    arc_id: str
    source_type: str
    source_id: str
    relation: str

class TruthIn(BaseModel):
    key: str
    statement: str
    state: TruthState = "provisional"
    context_policy: ContextPolicy = "scoped"
    visibility: str = "gm"
    temporal_context: str = "current"
    source: str = "manual"
    supersedes_id: UUID | None = None

class TruthPatch(BaseModel):
    statement: str | None = None
    state: TruthState | None = None
    context_policy: ContextPolicy | None = None
    visibility: str | None = None
    temporal_context: str | None = None
    supersedes_id: UUID | None = None

class TruthResponse(BaseModel):
    id: str
    key: str
    statement: str
    state: TruthState
    context_policy: ContextPolicy
    visibility: str
    temporal_context: str
    source: str
    supersedes_id: str | None

class SupersedeIn(BaseModel):
    replacement_id: UUID

class ContextPacketIn(BaseModel):
    task: str
    target: str = ""
    explicit: bool = False

class ProposalIn(BaseModel):
    title: str
    task: str = ""
    target_type: str
    target_id: str = ""
    proposed_changes: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    context_checksum: str = ""
    target_surface: str = "postgres"
    state: ProposalState = "pending_review"

class DecisionIn(BaseModel):
    decision: Literal["accept", "reject", "supersede"]
    note: str = ""

class ProposalResponse(BaseModel):
    id: str
    title: str
    task: str
    target_type: str
    target_id: str
    state: ProposalState
    proposed_changes: dict[str, Any]
    context_snapshot: dict[str, Any]
    context_checksum: str
    target_surface: str
    decision: dict[str, Any]
