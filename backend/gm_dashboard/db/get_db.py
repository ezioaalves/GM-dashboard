from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SASession


def _db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm",
    )


def get_connection():
    conn = psycopg2.connect(_db_url())
    conn.autocommit = True
    return conn


# SQLAlchemy engine — used by Alembic env.py and future routers
engine = create_engine(_db_url())
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> SASession:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
