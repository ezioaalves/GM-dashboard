from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from uuid import UUID

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .db.get_db import get_connection
from .sync_router import SyncReviewApplyRequest, apply_sync_review
from .system_enums import (
    ASSET_MIRROR_STATES,
    ASSET_STATUSES,
    FRESHNESS_STATES,
    GRAPH_ENDPOINT_TYPES,
    RELATIONSHIP_DIRECTIONS,
    RELATIONSHIP_PROVENANCES,
    REVIEW_STATUSES,
    SOURCE_SURFACES,
    VISIBILITIES,
)
from . import services
from .asset_scan import scan_assets
from .lore_scan import scan_vault

router = APIRouter()


class SourceCreate(BaseModel):
    source_surface: str = "vault"
    source_path: str
    source_hash: str = ""
    source_mtime: datetime | None = None
    source_kind: str = "markdown"
    title: str = ""
    visibility: str = "gm"
    freshness_state: str = "unknown"
    review_status: str = "pending"
    metadata: dict[str, Any] = {}


class SourcePatch(BaseModel):
    source_surface: str | None = None
    source_path: str | None = None
    source_hash: str | None = None
    source_mtime: datetime | None = None
    source_kind: str | None = None
    title: str | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    review_status: str | None = None
    metadata: dict[str, Any] | None = None


class EntityCreate(BaseModel):
    slug: str | None = None
    title: str
    entity_type: str = "article"
    summary: str = ""
    primary_source_id: UUID | None = None
    source_path: str = ""
    source_hash: str = ""
    visibility: str = "gm"
    freshness_state: str = "unknown"
    review_status: str = "accepted"
    metadata: dict[str, Any] = {}


class EntityPatch(BaseModel):
    title: str | None = None
    entity_type: str | None = None
    summary: str | None = None
    primary_source_id: UUID | None = None
    source_path: str | None = None
    source_hash: str | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    review_status: str | None = None
    metadata: dict[str, Any] | None = None


class AliasCreate(BaseModel):
    alias: str
    alias_kind: str = "name"
    locale: str = ""
    review_status: str = "accepted"


class AliasPatch(BaseModel):
    entity_id: UUID | None = None
    alias: str | None = None
    alias_kind: str | None = None
    locale: str | None = None
    review_status: str | None = None


class SectionCreate(BaseModel):
    source_id: UUID
    heading: str = ""
    body: str = ""
    section_order: int = 0
    heading_path: list[str] = []
    start_line: int | None = None
    end_line: int | None = None
    visibility: str = "gm"
    freshness_state: str = "unknown"
    review_status: str = "accepted"
    metadata: dict[str, Any] = {}


class SectionPatch(BaseModel):
    source_id: UUID | None = None
    entity_id: UUID | None = None
    heading: str | None = None
    body: str | None = None
    section_order: int | None = None
    heading_path: list[str] | None = None
    start_line: int | None = None
    end_line: int | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    review_status: str | None = None
    metadata: dict[str, Any] | None = None


class RelationshipCreate(BaseModel):
    source_type: str
    source_id: str
    target_type: str
    target_id: str = ""
    unresolved_target: str = ""
    relationship_type: str
    direction: str = "directed"
    provenance: str = "manual"
    confidence: float | None = None
    context: str = ""
    visibility: str = "gm"
    freshness_state: str = "unknown"
    review_status: str = "accepted"
    metadata: dict[str, Any] = {}


class RelationshipReviewCreate(BaseModel):
    source_surface: str = "manual"
    target_surface: str = "postgres"
    base_version: str = ""
    current_version: str = ""
    relationships: list[RelationshipCreate]
    conflict_flags: list[str] = []
    metadata: dict[str, Any] = {}


class LoreImportReviewCreate(BaseModel):
    source_surface: str = "vault"
    target_surface: str = "postgres"
    target_type: str = "entity"
    target_id: str = ""
    base_version: str = ""
    current_version: str = ""
    source_paths: list[str] = []
    proposed_changes: dict[str, Any] = {}
    conflict_flags: list[str] = []
    metadata: dict[str, Any] = {}


class RelationshipPatch(BaseModel):
    relationship_type: str | None = None
    direction: str | None = None
    provenance: str | None = None
    confidence: float | None = None
    context: str | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    review_status: str | None = None
    metadata: dict[str, Any] | None = None


class AssetCreate(BaseModel):
    source_path: str
    source_hash: str = ""
    asset_type: str = "image"
    usage: str = "reference"
    title: str = ""
    status: str = "current"
    visibility: str = "gm"
    freshness_state: str = "unknown"
    mirror_state: str = "not_mirrored"
    foundry_path: str = ""
    foundry_uuid: str = ""
    width: int | None = None
    height: int | None = None
    linked_entity_id: UUID | None = None
    review_status: str = "accepted"
    metadata: dict[str, Any] = {}


class AssetPatch(BaseModel):
    source_hash: str | None = None
    asset_type: str | None = None
    usage: str | None = None
    title: str | None = None
    status: str | None = None
    visibility: str | None = None
    freshness_state: str | None = None
    mirror_state: str | None = None
    foundry_path: str | None = None
    foundry_uuid: str | None = None
    width: int | None = None
    height: int | None = None
    linked_entity_id: UUID | None = None
    review_status: str | None = None
    metadata: dict[str, Any] | None = None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "entity"


def _json(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return value


def _validate(value: str, allowed: set[str], field: str) -> None:
    if value not in allowed:
        raise HTTPException(status_code=422, detail=f"{field} must be one of {sorted(allowed)}")


def _normalize_endpoint_id(endpoint_type: str, endpoint_id: str, field: str) -> str:
    if not endpoint_id:
        return ""
    if ":" in endpoint_id:
        prefix, raw_id = endpoint_id.split(":", 1)
        if prefix != endpoint_type or not raw_id:
            raise HTTPException(
                status_code=422,
                detail=f"{field} must be a {endpoint_type} graph endpoint id",
            )
        return endpoint_id
    return f"{endpoint_type}:{endpoint_id}"


def _normalize_endpoint_filter(
    endpoint_type: str | None, endpoint_id: str | None, type_field: str, id_field: str
) -> str | None:
    if endpoint_type is not None:
        _validate(endpoint_type, GRAPH_ENDPOINT_TYPES, type_field)
    if endpoint_id is None:
        return None
    if endpoint_type is None:
        return endpoint_id
    return _normalize_endpoint_id(endpoint_type, endpoint_id, id_field)


def _entity_row(row: dict) -> dict:
    data = dict(row)
    data["metadata"] = data.pop("metadata", {}) or {}
    return _json(data)


def _relationship_row(row: dict) -> dict:
    data = dict(row)
    data["metadata"] = data.pop("metadata", {}) or {}
    return _json(data)


def _asset_row(row: dict) -> dict:
    data = dict(row)
    data["metadata"] = data.pop("metadata", {}) or {}
    return _json(data)


def _source_row(row: dict) -> dict:
    data = dict(row)
    data["metadata"] = data.pop("metadata", {}) or {}
    return _json(data)


def _section_row(row: dict) -> dict:
    data = dict(row)
    data["metadata"] = data.pop("metadata", {}) or {}
    return _json(data)


def _alias_row(row: dict) -> dict:
    return _json(dict(row))


def _normalized_relationship_payload(payload: RelationshipCreate) -> dict[str, Any]:
    _validate(payload.source_type, GRAPH_ENDPOINT_TYPES, "source_type")
    _validate(payload.target_type, GRAPH_ENDPOINT_TYPES, "target_type")
    _validate(payload.direction, RELATIONSHIP_DIRECTIONS, "direction")
    _validate(payload.provenance, RELATIONSHIP_PROVENANCES, "provenance")
    _validate(payload.visibility, VISIBILITIES, "visibility")
    _validate(payload.freshness_state, FRESHNESS_STATES, "freshness_state")
    _validate(payload.review_status, REVIEW_STATUSES, "review_status")
    if not payload.target_id and not payload.unresolved_target:
        raise HTTPException(status_code=422, detail="target_id or unresolved_target is required")
    data = payload.model_dump()
    data["source_id"] = _normalize_endpoint_id(payload.source_type, payload.source_id, "source_id")
    data["target_id"] = _normalize_endpoint_id(payload.target_type, payload.target_id, "target_id")
    return data


def _get_entity_or_404(cur, entity_id: str) -> dict:
    cur.execute("SELECT * FROM lore_entities WHERE id = %s", (entity_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Entity not found")
    return _entity_row(row)


def _get_source_or_404(cur, source_id: str) -> dict:
    cur.execute("SELECT * FROM lore_sources WHERE id = %s", (source_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_row(row)


def _get_section_or_404(cur, section_id: str) -> dict:
    cur.execute("SELECT * FROM lore_sections WHERE id = %s", (section_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    return _section_row(row)


def _get_alias_or_404(cur, alias_id: str) -> dict:
    cur.execute("SELECT * FROM lore_aliases WHERE id = %s", (alias_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Alias not found")
    return _alias_row(row)


@router.get("/lore/sources")
def list_sources(
    source_surface: str | None = None,
    source_kind: str | None = None,
    visibility: str | None = None,
    freshness_state: str | None = None,
    review_status: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: list[Any] = []
            for column, value in (
                ("source_surface", source_surface),
                ("source_kind", source_kind),
                ("visibility", visibility),
                ("freshness_state", freshness_state),
                ("review_status", review_status),
            ):
                if value:
                    conditions.append(f"{column} = %s")
                    params.append(value)
            if q:
                conditions.append("(title ILIKE %s OR source_path ILIKE %s)")
                pattern = f"%{q}%"
                params.extend([pattern, pattern])
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(max(1, min(limit, 500)))
            cur.execute(
                f"""
                SELECT *
                FROM lore_sources
                {where}
                ORDER BY source_path ASC
                LIMIT %s
                """,
                params,
            )
            return [_source_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("/lore/sources", status_code=201)
def create_source(payload: SourceCreate) -> dict:
    _validate(payload.source_surface, SOURCE_SURFACES, "source_surface")
    _validate(payload.visibility, VISIBILITIES, "visibility")
    _validate(payload.freshness_state, FRESHNESS_STATES, "freshness_state")
    _validate(payload.review_status, REVIEW_STATUSES, "review_status")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_sources (
                  source_surface, source_path, source_hash, source_mtime, source_kind,
                  title, visibility, freshness_state, review_status, metadata
                )
                VALUES (
                  %(source_surface)s, %(source_path)s, %(source_hash)s, %(source_mtime)s,
                  %(source_kind)s, %(title)s, %(visibility)s, %(freshness_state)s,
                  %(review_status)s, %(metadata)s
                )
                RETURNING *
                """,
                {
                    **payload.model_dump(exclude={"metadata"}),
                    "metadata": psycopg2.extras.Json(payload.metadata),
                },
            )
            return _source_row(cur.fetchone())
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Source path already exists for surface")
    finally:
        conn.close()


@router.get("/lore/sources/{source_id}")
def get_source(source_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            source = _get_source_or_404(cur, str(source_id))
            cur.execute(
                """
                SELECT *
                FROM lore_entities
                WHERE primary_source_id = %s OR source_path = %s
                ORDER BY title ASC
                """,
                (str(source_id), source["source_path"]),
            )
            source["entities"] = [_entity_row(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT *
                FROM lore_sections
                WHERE source_id = %s
                ORDER BY section_order ASC, heading ASC
                """,
                (str(source_id),),
            )
            source["sections"] = [_json(dict(row)) for row in cur.fetchall()]
            return source
    finally:
        conn.close()


@router.patch("/lore/sources/{source_id}")
def patch_source(source_id: UUID, payload: SourcePatch) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    for field, allowed in (
        ("source_surface", SOURCE_SURFACES),
        ("visibility", VISIBILITIES),
        ("freshness_state", FRESHNESS_STATES),
        ("review_status", REVIEW_STATUSES),
    ):
        if field in updates and updates[field] is not None:
            _validate(updates[field], allowed, field)
    if not updates:
        return get_source(source_id)

    assignments: list[str] = []
    params: dict[str, Any] = {"id": str(source_id)}
    for key, value in updates.items():
        assignments.append(f"{key} = %({key})s")
        params[key] = psycopg2.extras.Json(value) if key == "metadata" else value
    assignments.append("updated_at = now()")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE lore_sources
                SET {", ".join(assignments)}
                WHERE id = %(id)s
                RETURNING *
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Source not found")
            return _source_row(row)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Source path already exists for surface")
    finally:
        conn.close()


@router.get("/lore/entities")
def list_entities(
    entity_type: str | None = None,
    visibility: str | None = None,
    freshness_state: str | None = None,
    review_status: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: list[Any] = []
            if entity_type:
                conditions.append("entity_type = %s")
                params.append(entity_type)
            if visibility:
                conditions.append("visibility = %s")
                params.append(visibility)
            if freshness_state:
                conditions.append("freshness_state = %s")
                params.append(freshness_state)
            if review_status:
                conditions.append("review_status = %s")
                params.append(review_status)
            if q:
                conditions.append("(title ILIKE %s OR slug ILIKE %s OR summary ILIKE %s)")
                pattern = f"%{q}%"
                params.extend([pattern, pattern, pattern])
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(max(1, min(limit, 500)))
            cur.execute(
                f"""
                SELECT *
                FROM lore_entities
                {where}
                ORDER BY title ASC
                LIMIT %s
                """,
                params,
            )
            return [_entity_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("/lore/entities", status_code=201)
def create_entity(payload: EntityCreate) -> dict:
    _validate(payload.visibility, VISIBILITIES, "visibility")
    _validate(payload.freshness_state, FRESHNESS_STATES, "freshness_state")
    _validate(payload.review_status, REVIEW_STATUSES, "review_status")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_entities (
                  slug, title, entity_type, summary, primary_source_id,
                  source_path, source_hash, visibility, freshness_state,
                  review_status, metadata
                )
                VALUES (
                  %(slug)s, %(title)s, %(entity_type)s, %(summary)s, %(primary_source_id)s,
                  %(source_path)s, %(source_hash)s, %(visibility)s, %(freshness_state)s,
                  %(review_status)s, %(metadata)s
                )
                RETURNING *
                """,
                {
                    "slug": payload.slug or _slugify(payload.title),
                    "title": payload.title,
                    "entity_type": payload.entity_type,
                    "summary": payload.summary,
                    "primary_source_id": str(payload.primary_source_id) if payload.primary_source_id else None,
                    "source_path": payload.source_path,
                    "source_hash": payload.source_hash,
                    "visibility": payload.visibility,
                    "freshness_state": payload.freshness_state,
                    "review_status": payload.review_status,
                    "metadata": psycopg2.extras.Json(payload.metadata),
                },
            )
            return _entity_row(cur.fetchone())
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Entity slug already exists")
    finally:
        conn.close()


@router.get("/lore/entities/{entity_id}")
def get_entity(entity_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            entity = _get_entity_or_404(cur, str(entity_id))
            cur.execute(
                "SELECT * FROM lore_aliases WHERE entity_id = %s ORDER BY alias ASC",
                (str(entity_id),),
            )
            entity["aliases"] = [_json(dict(row)) for row in cur.fetchall()]
            cur.execute(
                "SELECT * FROM lore_sections WHERE entity_id = %s ORDER BY section_order ASC, heading ASC",
                (str(entity_id),),
            )
            entity["sections"] = [_json(dict(row)) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT *
                FROM lore_relationships
                WHERE (source_type = 'entity' AND source_id IN (%s, %s))
                   OR (target_type = 'entity' AND target_id IN (%s, %s))
                ORDER BY created_at DESC
                """,
                (
                    str(entity_id),
                    entity["graph_endpoint_id"],
                    str(entity_id),
                    entity["graph_endpoint_id"],
                ),
            )
            entity["relationships"] = [_relationship_row(row) for row in cur.fetchall()]
            cur.execute(
                "SELECT * FROM lore_assets WHERE linked_entity_id = %s ORDER BY title ASC, source_path ASC",
                (str(entity_id),),
            )
            entity["assets"] = [_asset_row(row) for row in cur.fetchall()]
            return entity
    finally:
        conn.close()


@router.patch("/lore/entities/{entity_id}")
def patch_entity(entity_id: UUID, payload: EntityPatch) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    for field, allowed in (
        ("visibility", VISIBILITIES),
        ("freshness_state", FRESHNESS_STATES),
        ("review_status", REVIEW_STATUSES),
    ):
        if field in updates and updates[field] is not None:
            _validate(updates[field], allowed, field)
    if not updates:
        return get_entity(entity_id)

    assignments: list[str] = []
    params: dict[str, Any] = {"id": str(entity_id)}
    for key, value in updates.items():
        assignments.append(f"{key} = %({key})s")
        if key == "metadata":
            params[key] = psycopg2.extras.Json(value)
        elif isinstance(value, UUID):
            params[key] = str(value)
        else:
            params[key] = value
    assignments.append("updated_at = now()")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE lore_entities
                SET {", ".join(assignments)}
                WHERE id = %(id)s
                RETURNING *
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Entity not found")
            return _entity_row(row)
    finally:
        conn.close()


@router.post("/lore/entities/{entity_id}/aliases", status_code=201)
def create_alias(entity_id: UUID, payload: AliasCreate) -> dict:
    _validate(payload.review_status, REVIEW_STATUSES, "review_status")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _get_entity_or_404(cur, str(entity_id))
            cur.execute(
                """
                INSERT INTO lore_aliases (entity_id, alias, alias_kind, locale, review_status)
                VALUES (%(entity_id)s, %(alias)s, %(alias_kind)s, %(locale)s, %(review_status)s)
                RETURNING *
                """,
                {
                    "entity_id": str(entity_id),
                    "alias": payload.alias,
                    "alias_kind": payload.alias_kind,
                    "locale": payload.locale,
                    "review_status": payload.review_status,
                },
            )
            return _json(dict(cur.fetchone()))
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Alias already exists for entity and kind")
    finally:
        conn.close()


@router.get("/lore/aliases")
def list_aliases(
    entity_id: UUID | None = None,
    alias_kind: str | None = None,
    locale: str | None = None,
    review_status: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: list[Any] = []
            if entity_id:
                conditions.append("entity_id = %s")
                params.append(str(entity_id))
            for column, value in (
                ("alias_kind", alias_kind),
                ("locale", locale),
                ("review_status", review_status),
            ):
                if value is not None:
                    conditions.append(f"{column} = %s")
                    params.append(value)
            if q:
                conditions.append("alias ILIKE %s")
                params.append(f"%{q}%")
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(max(1, min(limit, 500)))
            cur.execute(
                f"""
                SELECT *
                FROM lore_aliases
                {where}
                ORDER BY alias ASC
                LIMIT %s
                """,
                params,
            )
            return [_alias_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.get("/lore/aliases/{alias_id}")
def get_alias(alias_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return _get_alias_or_404(cur, str(alias_id))
    finally:
        conn.close()


@router.patch("/lore/aliases/{alias_id}")
def patch_alias(alias_id: UUID, payload: AliasPatch) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if "review_status" in updates and updates["review_status"] is not None:
        _validate(updates["review_status"], REVIEW_STATUSES, "review_status")
    if not updates:
        return get_alias(alias_id)

    assignments: list[str] = []
    params: dict[str, Any] = {"id": str(alias_id)}
    for key, value in updates.items():
        assignments.append(f"{key} = %({key})s")
        params[key] = str(value) if isinstance(value, UUID) else value
    assignments.append("updated_at = now()")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE lore_aliases
                SET {", ".join(assignments)}
                WHERE id = %(id)s
                RETURNING *
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Alias not found")
            return _alias_row(row)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Alias already exists for entity and kind")
    finally:
        conn.close()


@router.get("/lore/sections")
def list_sections(
    source_id: UUID | None = None,
    entity_id: UUID | None = None,
    visibility: str | None = None,
    freshness_state: str | None = None,
    review_status: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: list[Any] = []
            if source_id:
                conditions.append("source_id = %s")
                params.append(str(source_id))
            if entity_id:
                conditions.append("entity_id = %s")
                params.append(str(entity_id))
            for column, value in (
                ("visibility", visibility),
                ("freshness_state", freshness_state),
                ("review_status", review_status),
            ):
                if value:
                    conditions.append(f"{column} = %s")
                    params.append(value)
            if q:
                conditions.append("(heading ILIKE %s OR body ILIKE %s)")
                pattern = f"%{q}%"
                params.extend([pattern, pattern])
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(max(1, min(limit, 500)))
            cur.execute(
                f"""
                SELECT *
                FROM lore_sections
                {where}
                ORDER BY section_order ASC, heading ASC
                LIMIT %s
                """,
                params,
            )
            return [_section_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.get("/lore/sections/{section_id}")
def get_section(section_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return _get_section_or_404(cur, str(section_id))
    finally:
        conn.close()


@router.patch("/lore/sections/{section_id}")
def patch_section(section_id: UUID, payload: SectionPatch) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    for field, allowed in (
        ("visibility", VISIBILITIES),
        ("freshness_state", FRESHNESS_STATES),
        ("review_status", REVIEW_STATUSES),
    ):
        if field in updates and updates[field] is not None:
            _validate(updates[field], allowed, field)
    if not updates:
        return get_section(section_id)

    assignments: list[str] = []
    params: dict[str, Any] = {"id": str(section_id)}
    for key, value in updates.items():
        assignments.append(f"{key} = %({key})s")
        if key == "metadata":
            params[key] = psycopg2.extras.Json(value)
        elif isinstance(value, UUID):
            params[key] = str(value)
        else:
            params[key] = value
    assignments.append("updated_at = now()")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE lore_sections
                SET {", ".join(assignments)}
                WHERE id = %(id)s
                RETURNING *
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Section not found")
            return _section_row(row)
    finally:
        conn.close()


@router.post("/lore/entities/{entity_id}/sections", status_code=201)
def create_section(entity_id: UUID, payload: SectionCreate) -> dict:
    _validate(payload.visibility, VISIBILITIES, "visibility")
    _validate(payload.freshness_state, FRESHNESS_STATES, "freshness_state")
    _validate(payload.review_status, REVIEW_STATUSES, "review_status")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _get_entity_or_404(cur, str(entity_id))
            cur.execute(
                """
                INSERT INTO lore_sections (
                  source_id, entity_id, heading, body, section_order, heading_path,
                  start_line, end_line, visibility, freshness_state, review_status, metadata
                )
                VALUES (
                  %(source_id)s, %(entity_id)s, %(heading)s, %(body)s, %(section_order)s,
                  %(heading_path)s, %(start_line)s, %(end_line)s, %(visibility)s,
                  %(freshness_state)s, %(review_status)s, %(metadata)s
                )
                RETURNING *
                """,
                {
                    "source_id": str(payload.source_id),
                    "entity_id": str(entity_id),
                    "heading": payload.heading,
                    "body": payload.body,
                    "section_order": payload.section_order,
                    "heading_path": payload.heading_path,
                    "start_line": payload.start_line,
                    "end_line": payload.end_line,
                    "visibility": payload.visibility,
                    "freshness_state": payload.freshness_state,
                    "review_status": payload.review_status,
                    "metadata": psycopg2.extras.Json(payload.metadata),
                },
            )
            return _json(dict(cur.fetchone()))
    finally:
        conn.close()


@router.get("/relationships")
def list_relationships(
    source_type: str | None = None,
    source_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    relationship_type: str | None = None,
    provenance: str | None = None,
    review_status: str | None = None,
    visibility: str | None = None,
    limit: int = 100,
) -> list[dict]:
    source_id = _normalize_endpoint_filter(source_type, source_id, "source_type", "source_id")
    target_id = _normalize_endpoint_filter(target_type, target_id, "target_type", "target_id")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: list[Any] = []
            for column, value in (
                ("source_type", source_type),
                ("source_id", source_id),
                ("target_type", target_type),
                ("target_id", target_id),
                ("relationship_type", relationship_type),
                ("provenance", provenance),
                ("review_status", review_status),
                ("visibility", visibility),
            ):
                if value is not None:
                    conditions.append(f"{column} = %s")
                    params.append(value)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(max(1, min(limit, 500)))
            cur.execute(
                f"""
                SELECT *
                FROM lore_relationships
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            return [_relationship_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("/relationships", status_code=201)
def create_relationship(payload: RelationshipCreate) -> dict:
    relationship = _normalized_relationship_payload(payload)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_relationships (
                  source_type, source_id, target_type, target_id, unresolved_target,
                  relationship_type, direction, provenance, confidence, context,
                  visibility, freshness_state, review_status, metadata
                )
                VALUES (
                  %(source_type)s, %(source_id)s, %(target_type)s, %(target_id)s,
                  %(unresolved_target)s, %(relationship_type)s, %(direction)s,
                  %(provenance)s, %(confidence)s, %(context)s, %(visibility)s,
                  %(freshness_state)s, %(review_status)s, %(metadata)s
                )
                RETURNING *
                """,
                {
                    **{key: value for key, value in relationship.items() if key != "metadata"},
                    "metadata": psycopg2.extras.Json(relationship["metadata"]),
                },
            )
            return _relationship_row(cur.fetchone())
    finally:
        conn.close()


@router.post("/relationships/review", status_code=201)
def create_relationship_review(payload: RelationshipReviewCreate) -> dict:
    _validate(payload.source_surface, SOURCE_SURFACES, "source_surface")
    _validate(payload.target_surface, SOURCE_SURFACES, "target_surface")
    if not payload.relationships:
        raise HTTPException(status_code=422, detail="relationships must contain at least one edge")

    relationships = [_normalized_relationship_payload(item) for item in payload.relationships]
    target_id = ""
    if len(relationships) == 1:
        target_id = (
            f"{relationships[0]['source_id']}->{relationships[0]['relationship_type']}"
            f"->{relationships[0]['target_id'] or relationships[0]['unresolved_target']}"
        )

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  base_version, current_version, proposed_changes, conflict_flags,
                  review_status
                )
                VALUES (
                  'relationship_change', %(source_surface)s, %(target_surface)s,
                  'relationship', %(target_id)s, %(base_version)s, %(current_version)s,
                  %(proposed_changes)s, %(conflict_flags)s, 'pending'
                )
                RETURNING *
                """,
                {
                    "source_surface": payload.source_surface,
                    "target_surface": payload.target_surface,
                    "target_id": target_id,
                    "base_version": payload.base_version,
                    "current_version": payload.current_version,
                    "proposed_changes": psycopg2.extras.Json(
                        {"relationships": relationships, "metadata": payload.metadata}
                    ),
                    "conflict_flags": psycopg2.extras.Json(payload.conflict_flags),
                },
            )
            return _json(dict(cur.fetchone()))
    finally:
        conn.close()


@router.post("/lore/import/review", status_code=201)
def create_lore_import_review(payload: LoreImportReviewCreate) -> dict:
    _validate(payload.source_surface, SOURCE_SURFACES, "source_surface")
    _validate(payload.target_surface, SOURCE_SURFACES, "target_surface")
    if payload.target_type not in GRAPH_ENDPOINT_TYPES and payload.target_type not in {
        "source",
        "section",
        "alias",
        "relationship",
    }:
        raise HTTPException(status_code=422, detail="target_type must be a lore import target")

    proposed_changes = {
        **payload.proposed_changes,
        "source_paths": payload.source_paths,
        "metadata": payload.metadata,
    }
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  base_version, current_version, proposed_changes, conflict_flags,
                  review_status
                )
                VALUES (
                  'vault_import', %(source_surface)s, %(target_surface)s,
                  %(target_type)s, %(target_id)s, %(base_version)s,
                  %(current_version)s, %(proposed_changes)s, %(conflict_flags)s,
                  'pending'
                )
                RETURNING *
                """,
                {
                    "source_surface": payload.source_surface,
                    "target_surface": payload.target_surface,
                    "target_type": payload.target_type,
                    "target_id": payload.target_id,
                    "base_version": payload.base_version,
                    "current_version": payload.current_version,
                    "proposed_changes": psycopg2.extras.Json(proposed_changes),
                    "conflict_flags": psycopg2.extras.Json(payload.conflict_flags),
                },
            )
            return _json(dict(cur.fetchone()))
    finally:
        conn.close()


@router.post("/lore/import/{review_id}/apply")
def apply_lore_import_review(review_id: UUID, payload: SyncReviewApplyRequest) -> dict:
    return apply_sync_review(review_id, payload)


@router.post("/lore/import/scan")
def scan_lore_vault(dry_run: bool = False) -> dict:
    vault_root = services.find_vault_root()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if dry_run:
                return scan_vault(vault_root, cur, dry_run=True)

            cur.execute(
                """
                INSERT INTO sync_jobs (
                  target, direction, status, diff, job_type,
                  source_surface, target_surface, started_at, updated_at
                )
                VALUES (
                  'lore:vault', 'vault_to_postgres', 'running', '', 'vault_scan',
                  'vault', 'postgres', now(), now()
                )
                RETURNING id
                """
            )
            job_id = str(cur.fetchone()["id"])

            try:
                summary = scan_vault(vault_root, cur, dry_run=False)
            except Exception as exc:
                error_message = str(exc)
                cur.execute(
                    """
                    UPDATE sync_jobs
                    SET status = 'failed',
                        error = %(error)s,
                        error_code = 'scan_error',
                        error_message = %(error)s,
                        finished_at = now(),
                        updated_at = now()
                    WHERE id = %(id)s
                    """,
                    {"id": job_id, "error": error_message},
                )
                raise

            cur.execute(
                """
                UPDATE sync_jobs
                SET status = 'succeeded',
                    result = %(result)s,
                    result_payload = %(result)s,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = %(id)s
                """,
                {"id": job_id, "result": psycopg2.extras.Json(summary)},
            )
            return {**summary, "sync_job_id": job_id}
    finally:
        conn.close()


@router.post("/assets/import/scan")
def scan_assets_import(dry_run: bool = False) -> dict:
    vault_root = services.find_vault_root()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if dry_run:
                return scan_assets(vault_root, cur, dry_run=True)

            cur.execute(
                """
                INSERT INTO sync_jobs (
                  target, direction, status, diff, job_type,
                  source_surface, target_surface, started_at, updated_at
                )
                VALUES (
                  'assets:vault', 'vault_to_postgres', 'running', '', 'asset_scan',
                  'vault', 'postgres', now(), now()
                )
                RETURNING id
                """
            )
            job_id = str(cur.fetchone()["id"])

            try:
                summary = scan_assets(vault_root, cur, dry_run=False)
            except Exception as exc:
                error_message = str(exc)
                cur.execute(
                    """
                    UPDATE sync_jobs
                    SET status = 'failed',
                        error = %(error)s,
                        error_code = 'scan_error',
                        error_message = %(error)s,
                        finished_at = now(),
                        updated_at = now()
                    WHERE id = %(id)s
                    """,
                    {"id": job_id, "error": error_message},
                )
                raise

            cur.execute(
                """
                UPDATE sync_jobs
                SET status = 'succeeded',
                    result = %(result)s,
                    result_payload = %(result)s,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = %(id)s
                """,
                {"id": job_id, "result": psycopg2.extras.Json(summary)},
            )
            return {**summary, "sync_job_id": job_id}
    finally:
        conn.close()


@router.post("/assets/import/{review_id}/apply")
def apply_asset_import_review(review_id: UUID, payload: SyncReviewApplyRequest) -> dict:
    return apply_sync_review(review_id, payload)


@router.patch("/relationships/{relationship_id}")
def patch_relationship(relationship_id: UUID, payload: RelationshipPatch) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    for field, allowed in (
        ("direction", RELATIONSHIP_DIRECTIONS),
        ("provenance", RELATIONSHIP_PROVENANCES),
        ("visibility", VISIBILITIES),
        ("freshness_state", FRESHNESS_STATES),
        ("review_status", REVIEW_STATUSES),
    ):
        if field in updates and updates[field] is not None:
            _validate(updates[field], allowed, field)
    if not updates:
        raise HTTPException(status_code=422, detail="No relationship fields supplied")
    assignments: list[str] = []
    params: dict[str, Any] = {"id": str(relationship_id)}
    for key, value in updates.items():
        assignments.append(f"{key} = %({key})s")
        params[key] = psycopg2.extras.Json(value) if key == "metadata" else value
    assignments.append("updated_at = now()")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE lore_relationships
                SET {", ".join(assignments)}
                WHERE id = %(id)s
                RETURNING *
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Relationship not found")
            return _relationship_row(row)
    finally:
        conn.close()


@router.get("/assets")
def list_assets(
    linked_entity_id: UUID | None = None,
    visibility: str | None = None,
    freshness_state: str | None = None,
    mirror_state: str | None = None,
    usage: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions: list[str] = []
            params: list[Any] = []
            if linked_entity_id:
                conditions.append("linked_entity_id = %s")
                params.append(str(linked_entity_id))
            for column, value in (
                ("visibility", visibility),
                ("freshness_state", freshness_state),
                ("mirror_state", mirror_state),
                ("usage", usage),
            ):
                if value:
                    conditions.append(f"{column} = %s")
                    params.append(value)
            if q:
                conditions.append("(title ILIKE %s OR source_path ILIKE %s)")
                pattern = f"%{q}%"
                params.extend([pattern, pattern])
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(max(1, min(limit, 500)))
            cur.execute(
                f"""
                SELECT *
                FROM lore_assets
                {where}
                ORDER BY title ASC, source_path ASC
                LIMIT %s
                """,
                params,
            )
            return [_asset_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.get("/assets/{asset_id}")
def get_asset(asset_id: UUID) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM lore_assets WHERE id = %s", (str(asset_id),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Asset not found")
            return _asset_row(row)
    finally:
        conn.close()


@router.post("/assets", status_code=201)
def create_asset(payload: AssetCreate) -> dict:
    _validate(payload.status, ASSET_STATUSES, "status")
    _validate(payload.visibility, VISIBILITIES, "visibility")
    _validate(payload.freshness_state, FRESHNESS_STATES, "freshness_state")
    _validate(payload.mirror_state, ASSET_MIRROR_STATES, "mirror_state")
    _validate(payload.review_status, REVIEW_STATUSES, "review_status")
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO lore_assets (
                  source_path, source_hash, asset_type, usage, title, status,
                  visibility, freshness_state, mirror_state, foundry_path, foundry_uuid,
                  width, height, linked_entity_id, review_status, metadata
                )
                VALUES (
                  %(source_path)s, %(source_hash)s, %(asset_type)s, %(usage)s,
                  %(title)s, %(status)s, %(visibility)s, %(freshness_state)s,
                  %(mirror_state)s, %(foundry_path)s, %(foundry_uuid)s, %(width)s,
                  %(height)s, %(linked_entity_id)s, %(review_status)s, %(metadata)s
                )
                RETURNING *
                """,
                {
                    **payload.model_dump(exclude={"metadata", "linked_entity_id"}),
                    "linked_entity_id": str(payload.linked_entity_id) if payload.linked_entity_id else None,
                    "metadata": psycopg2.extras.Json(payload.metadata),
                },
            )
            return _asset_row(cur.fetchone())
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Asset source_path already exists")
    finally:
        conn.close()


@router.patch("/assets/{asset_id}")
def patch_asset(asset_id: UUID, payload: AssetPatch) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    for field, allowed in (
        ("status", ASSET_STATUSES),
        ("visibility", VISIBILITIES),
        ("freshness_state", FRESHNESS_STATES),
        ("mirror_state", ASSET_MIRROR_STATES),
        ("review_status", REVIEW_STATUSES),
    ):
        if field in updates and updates[field] is not None:
            _validate(updates[field], allowed, field)
    if not updates:
        return get_asset(asset_id)
    assignments: list[str] = []
    params: dict[str, Any] = {"id": str(asset_id)}
    for key, value in updates.items():
        assignments.append(f"{key} = %({key})s")
        if key == "metadata":
            params[key] = psycopg2.extras.Json(value)
        elif isinstance(value, UUID):
            params[key] = str(value)
        else:
            params[key] = value
    assignments.append("updated_at = now()")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE lore_assets
                SET {", ".join(assignments)}
                WHERE id = %(id)s
                RETURNING *
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Asset not found")
            return _asset_row(row)
    finally:
        conn.close()
