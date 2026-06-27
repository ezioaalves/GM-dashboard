from __future__ import annotations

from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from .db.get_db import get_connection

router = APIRouter()

VALID_TYPES = {"Hard", "Soft", "Cut", "Added", "Replacement", "Spotlight", "Bridge", ""}
VALID_STATUSES = {"Draft", "Ready", "Played", "Cut"}


class SceneCreate(BaseModel):
    title: str = ""
    type: str = ""
    status: str = "Draft"
    session_id: Optional[int] = None
    description: str = ""
    location: list[str] = []
    cast: list[str] = []
    clock: list[str] = []
    cuttable: bool = False
    purpose: str = ""
    pc_pressure: str = ""
    entry_pressure: str = ""
    exit_condition: str = ""
    core_clue: str = ""
    superior_clue: str = ""
    optional_clue: str = ""
    false_lead: str = ""
    opening_image: str = ""
    sensory_words: str = ""
    interactable_objects: str = ""
    rules_likely: str = ""
    foundry_needs: str = ""
    replacement_route: str = ""
    if_succeed: str = ""
    if_fail: str = ""
    if_ignore: str = ""
    if_short: str = ""
    notes: str = ""
    pinned_material: list[dict] = []

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"Invalid type: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class SceneSessionPatch(BaseModel):
    session_id: Optional[int] = None


def _row_to_dict(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "type": row["type"],
        "status": row["status"],
        "session_id": row["session_id"],
        "description": row["description"],
        "location": list(row["location"] or []),
        "cast": list(row["cast"] or []),
        "clock": list(row["clock"] or []),
        "cuttable": row["cuttable"],
        "purpose": row["purpose"] or "",
        "pc_pressure": row["pc_pressure"] or "",
        "entry_pressure": row["entry_pressure"] or "",
        "exit_condition": row["exit_condition"] or "",
        "core_clue": row["core_clue"] or "",
        "superior_clue": row["superior_clue"] or "",
        "optional_clue": row["optional_clue"] or "",
        "false_lead": row["false_lead"] or "",
        "opening_image": row["opening_image"] or "",
        "sensory_words": row["sensory_words"] or "",
        "interactable_objects": row["interactable_objects"] or "",
        "rules_likely": row["rules_likely"] or "",
        "foundry_needs": row["foundry_needs"] or "",
        "replacement_route": row["replacement_route"] or "",
        "if_succeed": row["if_succeed"] or "",
        "if_fail": row["if_fail"] or "",
        "if_ignore": row["if_ignore"] or "",
        "if_short": row["if_short"] or "",
        "notes": row["notes"] or "",
        "pinned_material": list(row["pinned_material"] or []),
    }


@router.get("/scenes")
def list_scenes(session_id: int | None = None) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if session_id is not None:
                cur.execute("SELECT * FROM scenes WHERE session_id = %s ORDER BY created_at ASC", (session_id,))
            else:
                cur.execute("SELECT * FROM scenes ORDER BY created_at ASC")
            return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM scenes WHERE id = %s", (scene_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
            return _row_to_dict(row)
    finally:
        conn.close()


@router.post("/scenes", status_code=201)
def create_scene(payload: SceneCreate) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO scenes (
                  title, type, status, session_id, description,
                  location, "cast", "clock", cuttable, purpose, pc_pressure,
                  entry_pressure, exit_condition, core_clue, superior_clue,
                  optional_clue, false_lead, opening_image, sensory_words,
                  interactable_objects, rules_likely, foundry_needs,
                  replacement_route, if_succeed, if_fail, if_ignore, if_short,
                  notes, pinned_material
                ) VALUES (
                  %(title)s, %(type)s, %(status)s, %(session_id)s, %(description)s,
                  %(location)s, %(cast)s, %(clock)s, %(cuttable)s, %(purpose)s,
                  %(pc_pressure)s, %(entry_pressure)s, %(exit_condition)s,
                  %(core_clue)s, %(superior_clue)s, %(optional_clue)s,
                  %(false_lead)s, %(opening_image)s, %(sensory_words)s,
                  %(interactable_objects)s, %(rules_likely)s, %(foundry_needs)s,
                  %(replacement_route)s, %(if_succeed)s, %(if_fail)s,
                  %(if_ignore)s, %(if_short)s, %(notes)s, %(pinned_material)s
                ) RETURNING *
                """,
                {
                    "title": payload.title, "type": payload.type,
                    "status": payload.status, "session_id": payload.session_id,
                    "description": payload.description, "location": payload.location,
                    "cast": payload.cast, "clock": payload.clock,
                    "cuttable": payload.cuttable, "purpose": payload.purpose,
                    "pc_pressure": payload.pc_pressure,
                    "entry_pressure": payload.entry_pressure,
                    "exit_condition": payload.exit_condition,
                    "core_clue": payload.core_clue,
                    "superior_clue": payload.superior_clue,
                    "optional_clue": payload.optional_clue,
                    "false_lead": payload.false_lead,
                    "opening_image": payload.opening_image,
                    "sensory_words": payload.sensory_words,
                    "interactable_objects": payload.interactable_objects,
                    "rules_likely": payload.rules_likely,
                    "foundry_needs": payload.foundry_needs,
                    "replacement_route": payload.replacement_route,
                    "if_succeed": payload.if_succeed, "if_fail": payload.if_fail,
                    "if_ignore": payload.if_ignore, "if_short": payload.if_short,
                    "notes": payload.notes,
                    "pinned_material": psycopg2.extras.Json(payload.pinned_material),
                },
            )
            return _row_to_dict(cur.fetchone())
    finally:
        conn.close()


@router.put("/scenes/{scene_id}")
def update_scene(scene_id: int, payload: SceneCreate) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE scenes SET
                  title=%(title)s, type=%(type)s, status=%(status)s,
                  session_id=%(session_id)s, description=%(description)s,
                  location=%(location)s, "cast"=%(cast)s, "clock"=%(clock)s,
                  cuttable=%(cuttable)s, purpose=%(purpose)s,
                  pc_pressure=%(pc_pressure)s, entry_pressure=%(entry_pressure)s,
                  exit_condition=%(exit_condition)s, core_clue=%(core_clue)s,
                  superior_clue=%(superior_clue)s, optional_clue=%(optional_clue)s,
                  false_lead=%(false_lead)s, opening_image=%(opening_image)s,
                  sensory_words=%(sensory_words)s,
                  interactable_objects=%(interactable_objects)s,
                  rules_likely=%(rules_likely)s, foundry_needs=%(foundry_needs)s,
                  replacement_route=%(replacement_route)s,
                  if_succeed=%(if_succeed)s, if_fail=%(if_fail)s,
                  if_ignore=%(if_ignore)s, if_short=%(if_short)s,
                  notes=%(notes)s, pinned_material=%(pinned_material)s,
                  updated_at=now()
                WHERE id=%(id)s RETURNING *
                """,
                {
                    "id": scene_id, "title": payload.title, "type": payload.type,
                    "status": payload.status, "session_id": payload.session_id,
                    "description": payload.description, "location": payload.location,
                    "cast": payload.cast, "clock": payload.clock,
                    "cuttable": payload.cuttable, "purpose": payload.purpose,
                    "pc_pressure": payload.pc_pressure,
                    "entry_pressure": payload.entry_pressure,
                    "exit_condition": payload.exit_condition,
                    "core_clue": payload.core_clue,
                    "superior_clue": payload.superior_clue,
                    "optional_clue": payload.optional_clue,
                    "false_lead": payload.false_lead,
                    "opening_image": payload.opening_image,
                    "sensory_words": payload.sensory_words,
                    "interactable_objects": payload.interactable_objects,
                    "rules_likely": payload.rules_likely,
                    "foundry_needs": payload.foundry_needs,
                    "replacement_route": payload.replacement_route,
                    "if_succeed": payload.if_succeed, "if_fail": payload.if_fail,
                    "if_ignore": payload.if_ignore, "if_short": payload.if_short,
                    "notes": payload.notes,
                    "pinned_material": psycopg2.extras.Json(payload.pinned_material),
                },
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
            return _row_to_dict(row)
    finally:
        conn.close()


@router.patch("/scenes/{scene_id}/session")
def patch_scene_session(scene_id: int, payload: SceneSessionPatch) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE scenes SET session_id=%s, updated_at=now() WHERE id=%s RETURNING *",
                (payload.session_id, scene_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
            return _row_to_dict(row)
    finally:
        conn.close()


@router.delete("/scenes/{scene_id}")
def delete_scene(scene_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM scenes WHERE id=%s RETURNING id", (scene_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
            return {"deleted": True}
    finally:
        conn.close()
