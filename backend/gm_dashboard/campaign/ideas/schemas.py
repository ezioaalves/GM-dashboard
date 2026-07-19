from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator

IdeaState = Literal["captured", "triaged", "promoted", "discarded"]

class IdeaIn(BaseModel):
    title: str
    body: str = ""
    state: IdeaState = "captured"
    source: str = "quick_capture"
    arc_id: UUID | None = None
    target: dict[str, Any] = Field(default_factory=dict)
    visibility: str = "gm"

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

class IdeaPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    state: IdeaState | None = None
    arc_id: UUID | None = None
    target: dict[str, Any] | None = None
    visibility: str | None = None

    @model_validator(mode="after")
    def reject_null_non_nullable_fields(self) -> "IdeaPatch":
        for field in {"title", "body", "state", "target", "visibility"} & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} may not be null")
        if "title" in self.model_fields_set:
            self.title = self.title.strip() if self.title else self.title
            if not self.title:
                raise ValueError("title must not be blank")
        return self

class IdeaResponse(BaseModel):
    id: str
    title: str
    body: str
    state: IdeaState
    source: str
    arc_id: str | None
    target: dict[str, Any]
    visibility: str
    created_at: datetime | None
