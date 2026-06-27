from __future__ import annotations

import os
import pytest
import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from gm_dashboard.api import app

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@localhost:54329/kaihou_gm"
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tickets():
    """Wipe tickets table before each test."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tickets")
    conn.close()
    yield
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tickets")
    conn.close()


def seed_ticket(overrides: dict | None = None):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    base = {
        "id": "test-ticket",
        "title": "Test Ticket",
        "status": "open",
        "area": "docs",
        "priority": "med",
        "stage": "next",
        "next_action": "Do something",
    }
    if overrides:
        base.update(overrides)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tickets (id, title, status, area, priority, stage, next_action)
            VALUES (%(id)s, %(title)s, %(status)s, %(area)s, %(priority)s, %(stage)s, %(next_action)s)
            """,
            base,
        )
    conn.close()
    return base


def test_list_tickets_empty():
    res = client.get("/api/tickets")
    assert res.status_code == 200
    assert res.json() == []


def test_list_tickets_returns_seeded():
    seed_ticket()
    res = client.get("/api/tickets")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == "test-ticket"
    assert data[0]["title"] == "Test Ticket"


def test_list_tickets_filter_by_stage():
    seed_ticket({"id": "t-now", "stage": "now", "title": "Now ticket"})
    seed_ticket({"id": "t-next", "stage": "next", "title": "Next ticket"})
    res = client.get("/api/tickets?stage=now")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == "t-now"


def test_list_tickets_filter_by_area():
    seed_ticket({"id": "t-foundry", "area": "foundry", "title": "Foundry ticket"})
    seed_ticket({"id": "t-docs", "area": "docs", "title": "Docs ticket"})
    res = client.get("/api/tickets?area=foundry")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == "t-foundry"


def test_get_ticket_by_id():
    seed_ticket()
    res = client.get("/api/tickets/test-ticket")
    assert res.status_code == 200
    assert res.json()["id"] == "test-ticket"


def test_get_ticket_not_found():
    res = client.get("/api/tickets/does-not-exist")
    assert res.status_code == 404
