from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import GeneratorEntry, GeneratorTable

router = APIRouter()


class GeneratorEntryPatch(BaseModel):
    name: str | None = None
    description: str | None = None


def _entry_to_dict(entry: GeneratorEntry) -> dict:
    return {"roll": entry.roll, "name": entry.name, "description": entry.description}


def _table_to_dict(table: GeneratorTable) -> dict:
    return {
        "key": table.key,
        "label": table.label,
        "die": table.die,
        "entries": [_entry_to_dict(e) for e in table.entries],
    }


def _get_table_or_404(db: DBSession, key: str) -> GeneratorTable:
    table = db.query(GeneratorTable).filter(GeneratorTable.key == key).first()
    if not table:
        raise HTTPException(status_code=404, detail=f"Generator table '{key}' not found")
    return table


@router.get("/generator/tables")
def list_generator_tables(db: DBSession = Depends(get_db)) -> list[dict]:
    tables = db.query(GeneratorTable).order_by(GeneratorTable.key.asc()).all()
    return [_table_to_dict(t) for t in tables]


@router.post("/generator/tables/{key}/roll")
def roll_generator_table(key: str, db: DBSession = Depends(get_db)) -> dict:
    table = _get_table_or_404(db, key)
    if not table.entries:
        raise HTTPException(status_code=409, detail=f"Generator table '{key}' has no entries")
    entry = random.choice(table.entries)
    return _entry_to_dict(entry)


@router.patch("/generator/tables/{key}/entries/{roll}")
def patch_generator_entry(key: str, roll: int, payload: GeneratorEntryPatch, db: DBSession = Depends(get_db)) -> dict:
    table = _get_table_or_404(db, key)
    entry = next((e for e in table.entries if e.roll == roll), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Roll {roll} not found in table '{key}'")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return _entry_to_dict(entry)
