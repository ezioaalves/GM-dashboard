from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session as DBSession

from .db.get_db import get_db
from .db.models import LoreAsset, Scene
from .foundry_journals import create_journal, render_scene_journal_html, update_journal
from .relay_client import RelayError, load_relay_client

router = APIRouter()

VALID_TYPES = {"Hard", "Soft", "Cut", "Added", "Replacement", "Spotlight", "Bridge", ""}
VALID_SCENE_TYPES = {"hard", "soft", "cut", "added", "replacement", "spotlight", "bridge", ""}
SCENE_TYPE_ALIASES = {
    "Hard": "hard",
    "Core": "hard",
    "Soft": "soft",
    "Supplemental": "soft",
    "Cut": "cut",
    "Added": "added",
    "Extra": "added",
    "Replacement": "replacement",
    "Spotlight": "spotlight",
    "Bridge": "bridge",
    "": "",
}
VALID_STATUSES = {"Draft", "Ready", "Played", "Cut", "Replaced"}
VALID_PLACEMENTS = {"ordered", "floating", "backlog"}


def normalize_scene_type(value: str) -> str:
    if value in SCENE_TYPE_ALIASES:
        return SCENE_TYPE_ALIASES[value]
    lowered = value.lower()
    if lowered == "core":
        return "hard"
    if lowered == "extra":
        return "added"
    return lowered


def legacy_type(scene_type: str) -> str:
    if scene_type == "hard":
        return "Hard"
    if scene_type == "soft":
        return "Soft"
    if scene_type == "cut":
        return "Cut"
    if scene_type == "added":
        return "Added"
    if scene_type == "replacement":
        return "Replacement"
    if scene_type == "spotlight":
        return "Spotlight"
    if scene_type == "bridge":
        return "Bridge"
    return ""


class SceneCreate(BaseModel):
    title: str = ""
    type: str = ""
    scene_type: str | None = None
    status: str = "Draft"
    session_id: Optional[int] = None
    placement: str = "backlog"
    sort_order: int = 0
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
    cut_or_replace_plan: str = ""
    if_succeed: str = ""
    if_fail: str = ""
    if_ignore: str = ""
    if_short: str = ""
    notes: str = ""
    planned_notes: str = ""
    actual_notes: str = ""
    pinned_material: list[dict] = []

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_legacy_or_alias = v in VALID_TYPES or v in VALID_SCENE_TYPES or v in SCENE_TYPE_ALIASES
        if normalize_scene_type(v) not in VALID_SCENE_TYPES or not valid_legacy_or_alias:
            raise ValueError(f"Invalid type: {v}")
        return v

    @field_validator("scene_type")
    @classmethod
    def validate_scene_type(cls, v: str | None) -> str | None:
        if v is not None and normalize_scene_type(v) not in VALID_SCENE_TYPES:
            raise ValueError(f"Invalid scene_type: {v}")
        return normalize_scene_type(v) if v is not None else None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("placement")
    @classmethod
    def validate_placement(cls, v: str) -> str:
        if v not in VALID_PLACEMENTS:
            raise ValueError(f"Invalid placement: {v}")
        return v


class SceneSessionPatch(BaseModel):
    session_id: Optional[int] = None
    placement: str | None = None
    sort_order: int | None = None

    @field_validator("placement")
    @classmethod
    def validate_placement(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_PLACEMENTS:
            raise ValueError(f"Invalid placement: {v}")
        return v


def _scene_to_dict(scene: Scene) -> dict:
    return {
        "id": scene.id,
        "graph_endpoint_id": scene.graph_endpoint_id or f"scene:{scene.id}",
        "title": scene.title,
        "type": scene.type or legacy_type(scene.scene_type or ""),
        "scene_type": scene.scene_type or normalize_scene_type(scene.type or "soft") or "soft",
        "status": scene.status,
        "session_id": scene.session_id,
        "placement": scene.placement or "backlog",
        "sort_order": scene.sort_order or 0,
        "description": scene.description,
        "location": list(scene.location or []),
        "cast": list(scene.cast or []),
        "clock": list(scene.clock or []),
        "cuttable": scene.cuttable,
        "purpose": scene.purpose or "",
        "pc_pressure": scene.pc_pressure or "",
        "entry_pressure": scene.entry_pressure or "",
        "exit_condition": scene.exit_condition or "",
        "core_clue": scene.core_clue or "",
        "superior_clue": scene.superior_clue or "",
        "optional_clue": scene.optional_clue or "",
        "false_lead": scene.false_lead or "",
        "opening_image": scene.opening_image or "",
        "sensory_words": scene.sensory_words or "",
        "interactable_objects": scene.interactable_objects or "",
        "rules_likely": scene.rules_likely or "",
        "foundry_needs": scene.foundry_needs or "",
        "replacement_route": scene.replacement_route or "",
        "cut_or_replace_plan": scene.cut_or_replace_plan or scene.replacement_route or "",
        "if_succeed": scene.if_succeed or "",
        "if_fail": scene.if_fail or "",
        "if_ignore": scene.if_ignore or "",
        "if_short": scene.if_short or "",
        "notes": scene.notes or "",
        "planned_notes": scene.planned_notes or scene.planned_outcome or "",
        "actual_notes": scene.actual_notes or scene.actual_outcome or "",
        "body": scene.body or "",
        "clues": scene.clues or [],
        "planned_outcome": scene.planned_outcome or "",
        "actual_outcome": scene.actual_outcome or "",
        "foundry_export_status": scene.foundry_export_status or "not_exported",
        "foundry_journal_id": scene.foundry_journal_id or "",
        "source_path": scene.source_path or "",
        "source_hash": scene.source_hash or "",
        "visibility": scene.visibility or "gm",
        "freshness_state": scene.freshness_state or "unknown",
        "review_status": scene.review_status or "accepted",
        "pinned_material": list(scene.pinned_material or []),
    }


@router.get("/scenes")
def list_scenes(session_id: int | None = None, db: DBSession = Depends(get_db)) -> list[dict]:
    """
    List all scenes, optionally filtered by session_id.

    Query params:
      session_id: (optional) Filter to scenes in this session
    """
    query = db.query(Scene)

    if session_id is not None:
        query = query.filter(Scene.session_id == session_id)

    scenes = query.order_by(Scene.created_at.asc()).all()

    return [_scene_to_dict(scene) for scene in scenes]


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: int, db: DBSession = Depends(get_db)) -> dict:
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return _scene_to_dict(scene)


@router.post("/scenes", status_code=201)
def create_scene(payload: SceneCreate, db: DBSession = Depends(get_db)) -> dict:
    """Create a new scene."""
    scene_type = payload.scene_type or normalize_scene_type(payload.type or "soft") or "soft"
    type_value = payload.type if payload.type in VALID_TYPES else legacy_type(scene_type)
    cut_or_replace_plan = payload.cut_or_replace_plan or payload.replacement_route
    new_scene = Scene(
        title=payload.title,
        type=type_value,
        scene_type=scene_type,
        status=payload.status,
        session_id=payload.session_id,
        placement=payload.placement if payload.session_id is not None else "backlog",
        sort_order=payload.sort_order,
        description=payload.description,
        location=payload.location,
        cast=payload.cast,
        clock=payload.clock,
        cuttable=payload.cuttable,
        purpose=payload.purpose,
        pc_pressure=payload.pc_pressure,
        entry_pressure=payload.entry_pressure,
        exit_condition=payload.exit_condition,
        core_clue=payload.core_clue,
        superior_clue=payload.superior_clue,
        optional_clue=payload.optional_clue,
        false_lead=payload.false_lead,
        opening_image=payload.opening_image,
        sensory_words=payload.sensory_words,
        interactable_objects=payload.interactable_objects,
        rules_likely=payload.rules_likely,
        foundry_needs=payload.foundry_needs,
        replacement_route=payload.replacement_route,
        cut_or_replace_plan=cut_or_replace_plan,
        if_succeed=payload.if_succeed,
        if_fail=payload.if_fail,
        if_ignore=payload.if_ignore,
        if_short=payload.if_short,
        notes=payload.notes,
        planned_notes=payload.planned_notes,
        actual_notes=payload.actual_notes,
        pinned_material=payload.pinned_material,
    )
    db.add(new_scene)
    db.commit()
    db.refresh(new_scene)
    return _scene_to_dict(new_scene)


@router.put("/scenes/{scene_id}")
def update_scene(scene_id: int, payload: SceneCreate, db: DBSession = Depends(get_db)) -> dict:
    """Update scene fields (including session_id for drag-drop reorder)."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    scene_type = payload.scene_type or normalize_scene_type(payload.type or scene.scene_type or "soft") or "soft"
    type_value = payload.type if payload.type in VALID_TYPES else legacy_type(scene_type)
    cut_or_replace_plan = payload.cut_or_replace_plan or payload.replacement_route

    scene.title = payload.title
    scene.type = type_value
    scene.scene_type = scene_type
    scene.status = payload.status
    scene.session_id = payload.session_id
    scene.placement = payload.placement if payload.session_id is not None else "backlog"
    scene.sort_order = payload.sort_order
    scene.description = payload.description
    scene.location = payload.location
    scene.cast = payload.cast
    scene.clock = payload.clock
    scene.cuttable = payload.cuttable
    scene.purpose = payload.purpose
    scene.pc_pressure = payload.pc_pressure
    scene.entry_pressure = payload.entry_pressure
    scene.exit_condition = payload.exit_condition
    scene.core_clue = payload.core_clue
    scene.superior_clue = payload.superior_clue
    scene.optional_clue = payload.optional_clue
    scene.false_lead = payload.false_lead
    scene.opening_image = payload.opening_image
    scene.sensory_words = payload.sensory_words
    scene.interactable_objects = payload.interactable_objects
    scene.rules_likely = payload.rules_likely
    scene.foundry_needs = payload.foundry_needs
    scene.replacement_route = payload.replacement_route
    scene.cut_or_replace_plan = cut_or_replace_plan
    scene.if_succeed = payload.if_succeed
    scene.if_fail = payload.if_fail
    scene.if_ignore = payload.if_ignore
    scene.if_short = payload.if_short
    scene.notes = payload.notes
    scene.planned_notes = payload.planned_notes
    scene.actual_notes = payload.actual_notes
    scene.pinned_material = payload.pinned_material

    db.commit()
    db.refresh(scene)
    return _scene_to_dict(scene)


@router.patch("/scenes/{scene_id}/session")
def patch_scene_session(scene_id: int, payload: SceneSessionPatch, db: DBSession = Depends(get_db)) -> dict:
    """Update a scene's session_id (for drag-drop reorder)."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

    scene.session_id = payload.session_id
    if payload.placement is not None:
        scene.placement = payload.placement
    elif payload.session_id is None:
        scene.placement = "backlog"
    if payload.sort_order is not None:
        scene.sort_order = payload.sort_order
    db.commit()
    db.refresh(scene)
    return _scene_to_dict(scene)


@router.delete("/scenes/{scene_id}")
def delete_scene(scene_id: int, db: DBSession = Depends(get_db)) -> dict:
    """Delete a scene."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

    db.delete(scene)
    db.commit()
    return {"deleted": True}


class SceneForeignExportRequest(BaseModel):
    env: Literal["test", "prod"] = "test"


@router.post("/scenes/{scene_id}/foundry/export")
def export_scene_journal(
    scene_id: int, payload: SceneForeignExportRequest, db: DBSession = Depends(get_db)
) -> dict:
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

    pinned = list(scene.pinned_material or [])
    paths = [item["path"] for item in pinned if item.get("path")]
    mirrored_assets: list[dict] = []
    skipped_unmirrored: list[str] = []
    if paths:
        assets = db.query(LoreAsset).filter(LoreAsset.source_path.in_(paths)).all()
        by_path = {asset.source_path: asset for asset in assets}
        for path in paths:
            asset = by_path.get(path)
            if asset is not None and asset.mirror_state == "mirrored":
                mirrored_assets.append({"foundry_path": asset.foundry_path, "title": asset.title})
            else:
                skipped_unmirrored.append(path)

    scene_dict = _scene_to_dict(scene)
    html = render_scene_journal_html(scene_dict, mirrored_assets)

    try:
        client = load_relay_client(payload.env)
        if scene.foundry_journal_id:
            update_journal(client, scene.foundry_journal_id, html)
            journal_uuid = scene.foundry_journal_id
        else:
            journal_uuid = create_journal(client, scene_dict, html)
    except RelayError as exc:
        scene.foundry_export_status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    scene.foundry_journal_id = journal_uuid
    scene.foundry_export_status = "exported"
    db.commit()

    return {
        "exported": True,
        "foundry_journal_id": journal_uuid,
        "skipped_unmirrored": skipped_unmirrored,
    }
