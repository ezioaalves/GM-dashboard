from __future__ import annotations

import os

import psycopg2
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm")
from gm_dashboard.api import app

client = TestClient(app)

def clean() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"]); conn.autocommit = True
    with conn.cursor() as cursor: cursor.execute("DELETE FROM creative_ideas")
    conn.close()

@pytest.fixture(autouse=True)
def ideas_db():
    clean(); yield; clean()

def create(title: str, **extra):
    return client.post("/api/ideas", json={"title": title, **extra})

def test_idea_creation_filtering_editing_and_runtime_fields():
    first = create("First", body="line one\nline two", target={"kept": True}, visibility="gm").json()
    second = create("Second").json()
    assert client.get("/api/ideas").json()[0]["id"] == second["id"]
    assert first["target"] == {"kept": True} and first["visibility"] == "gm" and first["created_at"]
    edited = client.patch(f"/api/ideas/{first['id']}", json={"title": " Edited ", "body": "a\n\nb"})
    assert edited.status_code == 200 and edited.json()["title"] == "Edited" and edited.json()["body"] == "a\n\nb"
    assert client.get("/api/ideas?state=captured").json()

def test_lifecycle_idempotency_invalid_transition_and_legacy_promotion():
    idea = create("Workflow").json(); idea_id = idea["id"]
    invalid = client.patch(f"/api/ideas/{idea_id}", json={"state": "promoted"})
    assert invalid.status_code == 409 and invalid.json()["detail"]["code"] == "invalid_idea_transition"
    triaged = client.patch(f"/api/ideas/{idea_id}", json={"state": "triaged"}); assert triaged.status_code == 200
    promoted = client.post(f"/api/ideas/{idea_id}/promote"); assert promoted.status_code == 200 and promoted.json()["state"] == "promoted"
    assert client.post(f"/api/ideas/{idea_id}/promote").status_code == 200
    assert client.patch(f"/api/ideas/{idea_id}", json={"state": "triaged"}).status_code == 200
    assert client.patch(f"/api/ideas/{idea_id}", json={"state": "discarded"}).status_code == 200
    assert client.patch(f"/api/ideas/{idea_id}", json={"state": "captured"}).status_code == 200

@pytest.mark.parametrize("payload", [{"title": "   "}, {"title": "Valid", "body": None}, {"title": "Valid", "target": None}, {"title": "Valid", "state": "invalid"}])
def test_idea_validation_and_missing_records(payload):
    assert create(**payload).status_code == 422
    assert client.patch("/api/ideas/00000000-0000-0000-0000-000000000000", json={"title": "Nope"}).status_code == 404
