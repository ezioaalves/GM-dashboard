from __future__ import annotations

import enum

from sqlalchemy import (
    ARRAY, Boolean, Column, Date, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint, func, text,
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
    approved_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
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
    body = Column(Text, server_default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    number = Column(Integer, nullable=False, unique=True)
    name = Column(Text, nullable=False, server_default="")
    status = Column(String, default=SessionStatus.PLANNED.value, nullable=False)
    date = Column(Date)
    notes = Column(Text, nullable=False, server_default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    scenes = relationship("Scene", back_populates="session")
    session_note = relationship("SessionNote", back_populates="session", uselist=False)


class Scene(Base):
    __tablename__ = "scenes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False, server_default="")
    type = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="Draft")
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"))
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
    pinned_material = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

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
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    session = relationship("Session", back_populates="session_note")


# ── New tables (revision 002) ──────────────────────────────────────────────────

class Thread(Base):
    __tablename__ = "threads"
    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    arc = Column(Text)
    next_move = Column(Text)
    clock_label = Column(Text)
    clock_value = Column(Integer)
    clock_max = Column(Integer)
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
