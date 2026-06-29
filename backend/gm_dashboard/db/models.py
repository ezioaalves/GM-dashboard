from __future__ import annotations

import enum

from sqlalchemy import (
    ARRAY, Boolean, Column, Date, DateTime, ForeignKey,
    Float, Integer, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, relationship


class SessionStatus(str, enum.Enum):
    PLANNED = "Planned"
    ACTIVE = "Active"
    PLAYED = "Played"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(Text, nullable=False, unique=True)
    display_name = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, server_default="gm")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Draft(Base):
    __tablename__ = "drafts"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    kind = Column(Text, nullable=False)
    vault_path = Column(Text)
    status = Column(Text, nullable=False, server_default="draft")
    markdown = Column(Text, nullable=False, server_default="")
    source = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Projection(Base):
    __tablename__ = "projections"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(Text, nullable=False, unique=True)
    source_path = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source_mtime = Column(DateTime(timezone=True))
    refreshed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FoundryLink(Base):
    __tablename__ = "foundry_links"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    vault_path = Column(Text, nullable=False)
    foundry_uuid = Column(Text, nullable=False)
    link_kind = Column(Text, nullable=False)
    last_seen_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("vault_path", "foundry_uuid"),)


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    target = Column(Text, nullable=False)
    direction = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    diff = Column(Text, nullable=False, server_default="")
    job_type = Column(Text, nullable=False, server_default="legacy")
    source_surface = Column(Text, nullable=False, server_default="manual")
    target_surface = Column(Text, nullable=False, server_default="manual")
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    result = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error = Column(Text, nullable=False, server_default="")
    review_id = Column(PGUUID(as_uuid=True), ForeignKey("sync_reviews.id", ondelete="SET NULL"))
    input_payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    result_payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error_code = Column(Text, nullable=False, server_default="")
    error_message = Column(Text, nullable=False, server_default="")
    approved_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    approved_at = Column(DateTime(timezone=True))


class SheetRecord(Base):
    __tablename__ = "sheet_records"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    record_kind = Column(Text, nullable=False)
    vault_path = Column(Text)
    foundry_uuid = Column(Text)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="open")
    area = Column(Text, nullable=False)
    priority = Column(Text, nullable=False, server_default="med")
    stage = Column(Text, nullable=False, server_default="next")
    parent_id = Column(Text, ForeignKey("tickets.id"))
    threads = Column(ARRAY(Text), server_default=text("'{}'"))
    depends_on = Column(ARRAY(Text), server_default=text("'{}'"))
    next_action = Column(Text, server_default="")
    resume_note = Column(Text, server_default="")
    source = Column(Text, server_default="manual")
    introduced = Column(Date)
    closed = Column(Date)
    resolution = Column(Text, server_default="")
    review_after = Column(Date)
    lane = Column(Text, server_default="next")
    classification = Column(Text, server_default="")
    target_epic = Column(Text, server_default="")
    source_path = Column(Text, server_default="")
    source_hash = Column(Text, server_default="")
    source_mtime = Column(DateTime(timezone=True))
    review_status = Column(Text, server_default="accepted")
    body = Column(Text, server_default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class SyncReview(Base):
    __tablename__ = "sync_reviews"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    review_type = Column(Text, nullable=False)
    source_surface = Column(Text, nullable=False)
    target_surface = Column(Text, nullable=False)
    target_type = Column(Text, nullable=False)
    target_id = Column(Text, nullable=False, server_default="")
    base_version = Column(Text, nullable=False, server_default="")
    current_version = Column(Text, nullable=False, server_default="")
    proposed_changes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    conflict_flags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    review_status = Column(Text, nullable=False, server_default="pending")
    decision = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sync_job_id = Column(PGUUID(as_uuid=True), ForeignKey("sync_jobs.id", ondelete="SET NULL"))
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    updated_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at = Column(DateTime(timezone=True))
    applied_at = Column(DateTime(timezone=True))


class LoreSource(Base):
    __tablename__ = "lore_sources"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    source_surface = Column(Text, nullable=False, server_default="vault")
    source_path = Column(Text, nullable=False)
    source_hash = Column(Text, nullable=False, server_default="")
    source_mtime = Column(DateTime(timezone=True))
    source_kind = Column(Text, nullable=False, server_default="markdown")
    title = Column(Text, nullable=False, server_default="")
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="pending")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("source_surface", "source_path"),)


class LoreEntity(Base):
    __tablename__ = "lore_entities"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    graph_endpoint_id = Column(Text, nullable=False, unique=True, server_default="")
    slug = Column(Text, nullable=False, unique=True)
    title = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False, server_default="article")
    summary = Column(Text, nullable=False, server_default="")
    primary_source_id = Column(PGUUID(as_uuid=True), ForeignKey("lore_sources.id", ondelete="SET NULL"))
    source_path = Column(Text, nullable=False, server_default="")
    source_hash = Column(Text, nullable=False, server_default="")
    source_mtime = Column(DateTime(timezone=True))
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="pending")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LoreSection(Base):
    __tablename__ = "lore_sections"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    source_id = Column(PGUUID(as_uuid=True), ForeignKey("lore_sources.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(PGUUID(as_uuid=True), ForeignKey("lore_entities.id", ondelete="SET NULL"))
    heading = Column(Text, nullable=False, server_default="")
    body = Column(Text, nullable=False, server_default="")
    section_order = Column(Integer, nullable=False, server_default=text("0"))
    heading_path = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    start_line = Column(Integer)
    end_line = Column(Integer)
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="pending")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LoreAlias(Base):
    __tablename__ = "lore_aliases"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    entity_id = Column(PGUUID(as_uuid=True), ForeignKey("lore_entities.id", ondelete="CASCADE"), nullable=False)
    alias = Column(Text, nullable=False)
    alias_kind = Column(Text, nullable=False, server_default="name")
    locale = Column(Text, nullable=False, server_default="")
    review_status = Column(Text, nullable=False, server_default="accepted")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("entity_id", "alias", "alias_kind"),)


class LoreRelationship(Base):
    __tablename__ = "lore_relationships"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    source_type = Column(Text, nullable=False)
    source_id = Column(Text, nullable=False)
    target_type = Column(Text, nullable=False)
    target_id = Column(Text, nullable=False, server_default="")
    unresolved_target = Column(Text, nullable=False, server_default="")
    relationship_type = Column(Text, nullable=False)
    direction = Column(Text, nullable=False, server_default="directed")
    provenance = Column(Text, nullable=False, server_default="manual")
    confidence = Column(Float)
    context = Column(Text, nullable=False, server_default="")
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="pending")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LoreAsset(Base):
    __tablename__ = "lore_assets"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    graph_endpoint_id = Column(Text, nullable=False, unique=True, server_default="")
    source_path = Column(Text, nullable=False, unique=True)
    source_hash = Column(Text, nullable=False, server_default="")
    source_mtime = Column(DateTime(timezone=True))
    asset_type = Column(Text, nullable=False, server_default="image")
    usage = Column(Text, nullable=False, server_default="reference")
    title = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="current")
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    mirror_state = Column(Text, nullable=False, server_default="not_mirrored")
    foundry_path = Column(Text, nullable=False, server_default="")
    foundry_uuid = Column(Text, nullable=False, server_default="")
    width = Column(Integer)
    height = Column(Integer)
    linked_entity_id = Column(PGUUID(as_uuid=True), ForeignKey("lore_entities.id", ondelete="SET NULL"))
    review_status = Column(Text, nullable=False, server_default="pending")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    last_checked_at = Column(DateTime(timezone=True))
    last_mirrored_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    graph_endpoint_id = Column(Text, nullable=False, unique=True, server_default="")
    number = Column(Integer, nullable=False, unique=True)
    name = Column(Text, nullable=False, server_default="")
    status = Column(String, default=SessionStatus.PLANNED.value, nullable=False)
    date = Column(Date)
    notes = Column(Text, nullable=False, server_default="")
    summary = Column(Text, nullable=False, server_default="")
    prep_notes = Column(Text, nullable=False, server_default="")
    wrap_notes = Column(Text, nullable=False, server_default="")
    source_path = Column(Text, nullable=False, server_default="")
    source_hash = Column(Text, nullable=False, server_default="")
    source_mtime = Column(DateTime(timezone=True))
    played_at = Column(DateTime(timezone=True))
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="accepted")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    scenes = relationship("Scene", back_populates="session")
    session_note = relationship("SessionNote", back_populates="session", uselist=False, cascade="all, delete-orphan")


class Scene(Base):
    __tablename__ = "scenes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    graph_endpoint_id = Column(Text, nullable=False, unique=True, server_default="")
    title = Column(Text, nullable=False, server_default="")
    type = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="Draft")
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"))
    placement = Column(Text, nullable=False, server_default="backlog")
    sort_order = Column(Integer, nullable=False, server_default=text("0"))
    description = Column(Text, nullable=False, server_default="")
    location = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    cast = Column("cast", ARRAY(Text), nullable=False, server_default=text("'{}'"))
    clock = Column("clock", ARRAY(Text), nullable=False, server_default=text("'{}'"))
    cuttable = Column(Boolean, nullable=False, server_default=text("false"))
    purpose = Column(Text, nullable=False, server_default="")
    pc_pressure = Column(Text, nullable=False, server_default="")
    entry_pressure = Column(Text, nullable=False, server_default="")
    exit_condition = Column(Text, nullable=False, server_default="")
    core_clue = Column(Text, nullable=False, server_default="")
    superior_clue = Column(Text, nullable=False, server_default="")
    optional_clue = Column(Text, nullable=False, server_default="")
    false_lead = Column(Text, nullable=False, server_default="")
    opening_image = Column(Text, nullable=False, server_default="")
    sensory_words = Column(Text, nullable=False, server_default="")
    interactable_objects = Column(Text, nullable=False, server_default="")
    rules_likely = Column(Text, nullable=False, server_default="")
    foundry_needs = Column(Text, nullable=False, server_default="")
    replacement_route = Column(Text, nullable=False, server_default="")
    if_succeed = Column(Text, nullable=False, server_default="")
    if_fail = Column(Text, nullable=False, server_default="")
    if_ignore = Column(Text, nullable=False, server_default="")
    if_short = Column(Text, nullable=False, server_default="")
    notes = Column(Text, nullable=False, server_default="")
    body = Column(Text, nullable=False, server_default="")
    clues = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    planned_outcome = Column(Text, nullable=False, server_default="")
    actual_outcome = Column(Text, nullable=False, server_default="")
    foundry_export_status = Column(Text, nullable=False, server_default="not_exported")
    foundry_journal_id = Column(Text, nullable=False, server_default="")
    source_path = Column(Text, nullable=False, server_default="")
    source_hash = Column(Text, nullable=False, server_default="")
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="accepted")
    pinned_material = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    session = relationship("Session", back_populates="scenes")


class SessionNote(Base):
    __tablename__ = "session_notes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    scenes = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    npcs_present = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    clues_discovered = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    threads_touched = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    unresolved_questions = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    next_session_hook = Column(Text, nullable=False, server_default="")
    memory = Column(Text, nullable=False, server_default="")
    markdown = Column(Text, nullable=False, server_default="")
    target_path = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="draft")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    session = relationship("Session", back_populates="session_note")


# ── New tables (revision 002) ──────────────────────────────────────────────────

class Thread(Base):
    __tablename__ = "threads"
    id = Column(Text, primary_key=True)
    graph_endpoint_id = Column(Text, nullable=False, unique=True, server_default="")
    title = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    priority = Column(Text, nullable=False, server_default="med")
    arc = Column(Text)
    theme = Column(Text, nullable=False, server_default="")
    pressure = Column(Text, nullable=False, server_default="")
    stakes = Column(Text, nullable=False, server_default="")
    next_move = Column(Text)
    clock_label = Column(Text)
    clock_value = Column(Integer)
    clock_max = Column(Integer)
    unresolved_questions = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    last_touched_at = Column(DateTime(timezone=True))
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="accepted")
    factions = Column(ARRAY(Text))
    sessions = Column(ARRAY(Integer))
    vault_path = Column(Text)
    body = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class NPC(Base):
    __tablename__ = "npcs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    role = Column(Text)
    affiliation = Column(Text)
    location = Column(Text)
    status = Column(Text)
    rank = Column(Text)
    tags = Column(ARRAY(Text))
    narrative = Column(Text)
    gm_secret = Column(Text)
    relationship_to_pcs = Column(JSONB)
    stats = Column(JSONB)
    img_path = Column(Text)
    vault_path = Column(Text)
    foundry_actor_id_test = Column(Text)
    foundry_actor_id_prod = Column(Text)
    foundry_sync_locked = Column(Boolean, server_default=text("false"))
    foundry_last_synced_at = Column(DateTime(timezone=True))
    foundry_pending_import = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class PC(Base):
    __tablename__ = "pcs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    player = Column(Text)
    level = Column(Integer)
    classes = Column(JSONB)
    stats = Column(JSONB)
    narrative = Column(Text)
    vault_path = Column(Text)
    img_path = Column(Text)
    foundry_actor_id_test = Column(Text)
    foundry_actor_id_prod = Column(Text)
    foundry_pending_import = Column(JSONB)
    foundry_last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
