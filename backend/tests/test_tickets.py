from __future__ import annotations

import os
import pytest
import psycopg2
import psycopg2.extras
from fastapi.testclient import TestClient

from gm_dashboard.api import app
from gm_dashboard import tickets_router

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm"
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tickets():
    """Wipe tickets table before each test."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
        cur.execute("DELETE FROM tickets")
    conn.close()
    yield
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sync_reviews")
        cur.execute("DELETE FROM sync_jobs")
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


def test_create_ticket():
    res = client.post("/api/tickets", json={
        "title": "New Ticket",
        "area": "docs",
        "stage": "now",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "New Ticket"
    assert data["stage"] == "now"
    assert data["id"] == "new-ticket"


def test_create_ticket_auto_dedup_id():
    client.post("/api/tickets", json={"title": "Dup", "area": "docs"})
    res = client.post("/api/tickets", json={"title": "Dup", "area": "docs"})
    assert res.status_code == 201
    assert res.json()["id"] == "dup-2"


def test_create_ticket_custom_id():
    res = client.post("/api/tickets", json={
        "id": "my-custom-id",
        "title": "Custom",
        "area": "foundry",
    })
    assert res.status_code == 201
    assert res.json()["id"] == "my-custom-id"


def test_update_ticket():
    seed_ticket()
    res = client.put("/api/tickets/test-ticket", json={
        "title": "Updated Title",
        "status": "in_progress",
        "area": "foundry",
        "priority": "high",
        "stage": "now",
        "next_action": "Ship it",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == "in_progress"
    assert data["area"] == "foundry"


def test_update_ticket_not_found():
    res = client.put("/api/tickets/ghost", json={
        "title": "Ghost",
        "status": "open",
        "area": "docs",
        "priority": "med",
        "stage": "next",
    })
    assert res.status_code == 404


def test_patch_stage():
    seed_ticket({"stage": "next"})
    res = client.patch("/api/tickets/test-ticket/stage", json={"stage": "now"})
    assert res.status_code == 200
    assert res.json()["stage"] == "now"


def test_patch_stage_invalid():
    seed_ticket()
    res = client.patch("/api/tickets/test-ticket/stage", json={"stage": "bogus"})
    assert res.status_code == 422


def test_delete_ticket():
    seed_ticket()
    res = client.delete("/api/tickets/test-ticket")
    assert res.status_code == 200
    assert res.json()["deleted"] is True
    assert client.get("/api/tickets/test-ticket").status_code == 404


def test_delete_ticket_not_found():
    res = client.delete("/api/tickets/ghost")
    assert res.status_code == 404


def test_update_ticket_invalid_area():
    seed_ticket()
    res = client.put("/api/tickets/test-ticket", json={
        "title": "X", "status": "open", "area": "bogus",
        "priority": "med", "stage": "next",
    })
    assert res.status_code == 422


def write_ticket_source(root, ticket_id: str = "system-core-data-spine"):
    tickets_dir = root / "Campaign Management" / "operational" / "tickets"
    tickets_dir.mkdir(parents=True)
    path = tickets_dir / f"{ticket_id}.md"
    path.write_text(
        """---
id: system-core-data-spine
title: "Implement Core Entity Spine And Review Models"
status: open
area: housekeeping
priority: high
stage: next
introduced: 2026-06-28
depends_on:
  - system-definition-backlog-map
---

Import this ticket through review.
""",
        encoding="utf-8",
    )
    mapping_dir = root / "docs" / "superpowers" / "system-definition"
    mapping_dir.mkdir(parents=True)
    (mapping_dir / "12-backlog-mapping.md").write_text(
        """# Backlog Mapping

## Operational Tickets

| Ticket | Classification | Target epic | Notes |
| --- | --- | --- | --- |
| `system-core-data-spine` | current | Epic 3 | Must use sync_reviews. |

## Dashboard Plans And Specs
""",
        encoding="utf-8",
    )
    return path


def test_stage_ticket_import_review_preserves_markdown(tmp_path, monkeypatch):
    source = write_ticket_source(tmp_path)
    monkeypatch.setattr(tickets_router, "_vault_root", lambda: tmp_path)

    res = client.post("/api/tickets/import/review")

    assert res.status_code == 201
    data = res.json()
    assert data["found"] == 1
    assert len(data["created"]) == 1
    assert data["source_files_deleted"] == 0
    assert source.exists()

    reviews = client.get("/api/sync/reviews?review_type=ticket_import").json()
    assert len(reviews) == 1
    review = client.get(f"/api/sync/reviews/{reviews[0]['id']}").json()
    assert review["review_status"] == "pending"
    assert review["source_surface"] == "vault"
    assert review["target_surface"] == "postgres"
    assert review["target_id"] == "system-core-data-spine"
    assert review["proposed_changes"]["source_preserved"] is True
    ticket = review["proposed_changes"]["ticket"]
    assert ticket["classification"] == "current"
    assert ticket["target_epic"] == "Epic 3"
    assert ticket["source_path"] == "Campaign Management/operational/tickets/system-core-data-spine.md"


def test_apply_accepted_ticket_import_keeps_source_file(tmp_path, monkeypatch):
    source = write_ticket_source(tmp_path)
    monkeypatch.setattr(tickets_router, "_vault_root", lambda: tmp_path)
    staged = client.post("/api/tickets/import/review").json()
    review_id = staged["created"][0]["review_id"]

    decision = client.patch(f"/api/sync/reviews/{review_id}", json={"review_status": "accepted"})
    assert decision.status_code == 200
    applied = client.post(
        f"/api/sync/reviews/{review_id}/apply",
        json={
            "confirmation": True,
            "selected_change_ids": ["ticket:system-core-data-spine"],
            "target_surface": "postgres",
        },
    )

    assert applied.status_code == 200
    assert applied.json()["source_files_deleted"] == 0
    assert source.exists()

    ticket = client.get("/api/tickets/system-core-data-spine").json()
    assert ticket["id"] == "system-core-data-spine"
    assert ticket["classification"] == "current"
    assert ticket["target_epic"] == "Epic 3"
    assert ticket["review_status"] == "accepted"
    assert ticket["source_path"] == "Campaign Management/operational/tickets/system-core-data-spine.md"

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT input_payload
                FROM sync_jobs
                WHERE review_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (review_id,),
            )
            job = cur.fetchone()
        assert job["input_payload"]["selected_change_ids"] == ["ticket:system-core-data-spine"]
        assert job["input_payload"]["target_surface"] == "postgres"
    finally:
        conn.close()
