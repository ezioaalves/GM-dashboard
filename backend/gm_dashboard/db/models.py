from __future__ import annotations

import enum

from sqlalchemy import (
    ARRAY, Boolean, Column, Date, DateTime, ForeignKey,
    Float, Integer, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, relationship


class SessionStatus(str, enum.Enum):
    PLANNED = "planned"
    READY = "ready"
    PLAYED = "played"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


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
    status = Column(Text, nullable=False, server_default="queued")
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
    promise = Column(Text, nullable=False, server_default="")
    fit_check = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    clue_map = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    wrap_capture = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    recap_seed = Column(Text, nullable=False, server_default="")
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
    scene_type = Column(Text, nullable=False, server_default="soft")
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
    cut_or_replace_plan = Column(Text, nullable=False, server_default="")
    if_succeed = Column(Text, nullable=False, server_default="")
    if_fail = Column(Text, nullable=False, server_default="")
    if_ignore = Column(Text, nullable=False, server_default="")
    if_short = Column(Text, nullable=False, server_default="")
    notes = Column(Text, nullable=False, server_default="")
    body = Column(Text, nullable=False, server_default="")
    clues = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    planned_notes = Column(Text, nullable=False, server_default="")
    actual_notes = Column(Text, nullable=False, server_default="")
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
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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


class Clock(Base):
    __tablename__ = "clocks"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    graph_endpoint_id = Column(Text, nullable=False, unique=True, server_default="")
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, server_default="")
    kind = Column(Text, nullable=False, server_default="progress")
    segments = Column(Integer, nullable=False)
    filled = Column(Integer, nullable=False, server_default=text("0"))
    segment_labels = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    lifecycle = Column(Text, nullable=False, server_default="active")
    resolution = Column(Text, nullable=False, server_default="")
    resolved_at = Column(DateTime(timezone=True))
    origin = Column(Text, nullable=False, server_default="manual")
    foundry_clock_id_test = Column(Text, nullable=False, server_default="")
    foundry_clock_id_prod = Column(Text, nullable=False, server_default="")
    mirror_state = Column(Text, nullable=False, server_default="not_mirrored")
    last_mirrored_at = Column(DateTime(timezone=True))
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="accepted")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClockTick(Base):
    __tablename__ = "clock_ticks"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    clock_id = Column(PGUUID(as_uuid=True), ForeignKey("clocks.id", ondelete="CASCADE"), nullable=False)
    delta = Column(Integer, nullable=False)
    filled_before = Column(Integer, nullable=False)
    filled_after = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    caused_by = Column(Text, nullable=False, server_default="manual")
    rule_id = Column(PGUUID(as_uuid=True), ForeignKey("cascade_rules.id", ondelete="SET NULL"))
    trigger_fire_id = Column(PGUUID(as_uuid=True), nullable=False)
    hop_depth = Column(Integer, nullable=False, server_default=text("0"))
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CascadeRule(Base):
    __tablename__ = "cascade_rules"
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(Text, nullable=False, unique=True)
    title = Column(Text, nullable=False, server_default="")
    description = Column(Text, nullable=False, server_default="")
    trigger_kind = Column(Text, nullable=False, server_default="manual")
    trigger_clock_id = Column(PGUUID(as_uuid=True), ForeignKey("clocks.id", ondelete="CASCADE"))
    trigger_event = Column(Text)
    condition = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    effects = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    enabled = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Adventure(Base):
    __tablename__ = "adventures"
    id = Column(Integer, primary_key=True, autoincrement=True)
    graph_endpoint_id = Column(Text, nullable=False, unique=True, server_default="")
    title = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="draft")
    current_arc = Column(Text, nullable=False, server_default="")
    pitch = Column(Text, nullable=False, server_default="")
    mode = Column(Text, nullable=False, server_default="")
    tone_rule = Column(Text, nullable=False, server_default="")
    safety_flags = Column(Text, nullable=False, server_default="")
    feel_target = Column(Text, nullable=False, server_default="")
    feel_avoid = Column(Text, nullable=False, server_default="")
    stakes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    location = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    spine = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    clue_map = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    foundry_needs = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    rules_notes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source_path = Column(Text, nullable=False, server_default="")
    source_hash = Column(Text, nullable=False, server_default="")
    source_mtime = Column(DateTime(timezone=True))
    visibility = Column(Text, nullable=False, server_default="gm")
    freshness_state = Column(Text, nullable=False, server_default="unknown")
    review_status = Column(Text, nullable=False, server_default="accepted")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    pc_pressure = relationship("AdventurePcPressure", cascade="all, delete-orphan", order_by="AdventurePcPressure.sort_order")
    rewards = relationship("AdventureReward", cascade="all, delete-orphan", order_by="AdventureReward.sort_order")
    clock_links = relationship("AdventureClockLink", cascade="all, delete-orphan")
    encounters = relationship("AdventureEncounter", cascade="all, delete-orphan", order_by="AdventureEncounter.sort_order")
    cast = relationship("AdventureCast", cascade="all, delete-orphan", order_by="AdventureCast.sort_order")


class AdventurePcPressure(Base):
    __tablename__ = "adventure_pc_pressure"
    id = Column(Integer, primary_key=True, autoincrement=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id", ondelete="CASCADE"), nullable=False)
    pc_id = Column(Integer, ForeignKey("pcs.id"), nullable=False)
    pressure = Column(Text, nullable=False, server_default="")
    growth = Column(Text, nullable=False, server_default="")
    cost = Column(Text, nullable=False, server_default="")
    sort_order = Column(Integer, nullable=False, server_default=text("0"))


class AdventureReward(Base):
    __tablename__ = "adventure_rewards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False, server_default="")
    type = Column(Text, nullable=False, server_default="")
    who_cares = Column(Text, nullable=False, server_default="")
    mechanical_note = Column(Text, nullable=False, server_default="")
    future_hook = Column(Text, nullable=False, server_default="")
    sort_order = Column(Integer, nullable=False, server_default=text("0"))


class AdventureClockLink(Base):
    __tablename__ = "adventure_clock_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id", ondelete="CASCADE"), nullable=False)
    clock_id = Column(PGUUID(as_uuid=True), ForeignKey("clocks.id", ondelete="SET NULL"))
    thread_id = Column(Text, ForeignKey("threads.id", ondelete="SET NULL"))
    how_it_appears = Column(Text, nullable=False, server_default="")
    advance_trigger = Column(Text, nullable=False, server_default="")
    visible_impact = Column(Text, nullable=False, server_default="")


class AdventureEncounter(Base):
    __tablename__ = "adventure_encounters"
    id = Column(Integer, primary_key=True, autoincrement=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False, server_default="")
    objective = Column(Text, nullable=False, server_default="")
    opposition = Column(Text, nullable=False, server_default="")
    terrain_constraint = Column(Text, nullable=False, server_default="")
    what_changes = Column(Text, nullable=False, server_default="")
    sort_order = Column(Integer, nullable=False, server_default=text("0"))


class AdventureCast(Base):
    __tablename__ = "adventure_cast"
    id = Column(Integer, primary_key=True, autoincrement=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id", ondelete="CASCADE"), nullable=False)
    npc_id = Column(Integer, ForeignKey("npcs.id"), nullable=False)
    role = Column(Text, nullable=False, server_default="")
    wants_now = Column(Text, nullable=False, server_default="")
    hides = Column(Text, nullable=False, server_default="")
    if_helped = Column(Text, nullable=False, server_default="")
    if_crossed = Column(Text, nullable=False, server_default="")
    sort_order = Column(Integer, nullable=False, server_default=text("0"))


class SessionAdventure(Base):
    __tablename__ = "session_adventures"
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id", ondelete="CASCADE"), primary_key=True)


class GeneratorTable(Base):
    __tablename__ = "generator_tables"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, nullable=False, unique=True)
    label = Column(Text, nullable=False)
    die = Column(Text, nullable=False)

    entries = relationship("GeneratorEntry", cascade="all, delete-orphan", order_by="GeneratorEntry.sort_order")


class GeneratorEntry(Base):
    __tablename__ = "generator_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("generator_tables.id", ondelete="CASCADE"), nullable=False)
    roll = Column(Integer, nullable=False)
    name = Column(Text, nullable=False, server_default="")
    description = Column(Text, nullable=False, server_default="")
    sort_order = Column(Integer, nullable=False, server_default=text("0"))


class PcLane(Base):
    __tablename__ = "pc_lanes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pc_id = Column(Integer, ForeignKey("pcs.id", ondelete="CASCADE"), nullable=False, unique=True)
    goal = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="active")
    pressure = Column(Text, nullable=False, server_default="")
    notes = Column(Text, nullable=False, server_default="")
    last_touched_session = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Risk(Base):
    __tablename__ = "risks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False, server_default="")
    description = Column(Text, nullable=False, server_default="")
    likelihood = Column(Text, nullable=False, server_default="medium")
    mitigation = Column(Text, nullable=False, server_default="")
    contingency = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="open")
    related_thread_id = Column(Text, ForeignKey("threads.id", ondelete="SET NULL"))
    related_pc_id = Column(Integer, ForeignKey("pcs.id", ondelete="SET NULL"))
    last_reviewed_session = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FeedbackEntry(Base):
    __tablename__ = "feedback_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_number = Column(Integer)
    cadence = Column(Text, nullable=False, server_default="quick_check")
    players_present = Column(Text, nullable=False, server_default="")
    more_of = Column(Text, nullable=False, server_default="")
    less_of = Column(Text, nullable=False, server_default="")
    clarify = Column(Text, nullable=False, server_default="")
    notes = Column(Text, nullable=False, server_default="")
    recorded_at = Column(Date, nullable=False, server_default=func.current_date())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    action_items = relationship(
        "FeedbackActionItem", cascade="all, delete-orphan", order_by="FeedbackActionItem.sort_order"
    )


class FeedbackActionItem(Base):
    __tablename__ = "feedback_action_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(Integer, ForeignKey("feedback_entries.id", ondelete="CASCADE"), nullable=False)
    item = Column(Text, nullable=False, server_default="")
    owner = Column(Text, nullable=False, server_default="")
    follow_up = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="open")
    sort_order = Column(Integer, nullable=False, server_default=text("0"))
