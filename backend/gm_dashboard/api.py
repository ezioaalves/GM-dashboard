from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import services


app = FastAPI(title="Kaihou GM Dashboard", version="0.1.0")


class SessionNoteRequest(BaseModel):
    memory: str = ""


class SceneRequest(BaseModel):
    title: str
    purpose: str = ""
    cast: list[str] = []
    clue: str = ""
    clock: str = ""
    foundry_needs: list[str] = []
    notes: str = ""


class SaveDraftRequest(BaseModel):
    target_path: str


class MarkdownSaveRequest(BaseModel):
    markdown: str


def handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except services.VaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/cockpit/session")
def get_cockpit_session() -> dict[str, Any]:
    return handle(services.cockpit_session)


@app.post("/api/capture/session-note")
def capture_session_note(payload: SessionNoteRequest) -> dict[str, Any]:
    return handle(services.draft_session_note, payload.memory)


@app.post("/api/capture/scene")
def capture_scene(payload: SceneRequest) -> dict[str, Any]:
    return handle(services.draft_scene, payload.model_dump())


@app.get("/api/search")
def search(q: str, limit: int = 20) -> list[dict[str, str]]:
    return handle(services.search_vault, q, limit=limit)


@app.get("/api/tickets")
def tickets() -> list[dict[str, Any]]:
    return handle(lambda: services.ticket_files(services.find_vault_root()))


@app.post("/api/drafts/{draft_id}/save")
def save_draft(draft_id: str, payload: SaveDraftRequest) -> dict[str, Any]:
    return handle(services.save_draft, draft_id, payload.target_path)


@app.get("/api/foundry/status")
def foundry_status() -> dict[str, Any]:
    return handle(lambda: services.foundry_status(services.find_vault_root()))


@app.get("/api/files/markdown")
def get_markdown_file(path: str) -> dict[str, str]:
    return handle(services.vault_markdown_file, path)


@app.put("/api/files/markdown")
def put_markdown_file(path: str, payload: MarkdownSaveRequest) -> dict[str, str]:
    return handle(services.save_vault_markdown_file, path, payload.markdown)
