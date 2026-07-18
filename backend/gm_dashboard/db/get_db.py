from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SASession


def _db_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required; configure the production PostgreSQL service.")
    return value


def get_connection():
    conn = psycopg2.connect(_db_url())
    conn.autocommit = True
    return conn


@contextmanager
def engine_connection():
    """Non-autocommit connection for clock-engine fires (real transaction).

    The engine's ``_run_fire`` owns commit/rollback — this manager never
    commits implicitly; it only guarantees rollback on an unhandled
    exception and always closes the connection. Use for any route that
    calls ``fire_manual_tick`` / ``fire_rule`` so the FOR UPDATE state
    load and all tick writes share one atomic transaction.
    """
    conn = psycopg2.connect(_db_url())
    conn.autocommit = False
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _connect_with_dsn():
    return psycopg2.connect(_db_url())


# SQLAlchemy engine — routes use SQLAlchemy sessions, while the local psycopg2
# build only connects reliably through a DSN string.
engine = create_engine(_db_url(), creator=_connect_with_dsn)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> SASession:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
