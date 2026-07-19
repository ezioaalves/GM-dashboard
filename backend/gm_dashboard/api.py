from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import services
from .tickets_router import router as tickets_router
from .scenes_router import router as scenes_router
from .sessions_router import router as sessions_router
from .sync_router import router as sync_router
from .lore_router import router as lore_router
from .threads_router import router as threads_router
from .clocks_router import router as clocks_router
from .adventures_router import router as adventures_router
from .generator_router import router as generator_router
from .npcs_router import router as npcs_router
from .pcs_router import router as pcs_router
from .pc_lanes_router import router as pc_lanes_router
from .risk_register_router import router as risk_register_router
from .feedback_router import router as feedback_router
from .campaign import router as campaign_router
from .system_enums import enum_catalog


app = FastAPI(title="Kaihou GM Dashboard", version="0.1.0")
app.include_router(tickets_router, prefix="/api")
app.include_router(scenes_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(lore_router, prefix="/api")
app.include_router(threads_router, prefix="/api")
app.include_router(clocks_router, prefix="/api")
app.include_router(adventures_router, prefix="/api")
app.include_router(generator_router, prefix="/api")
app.include_router(npcs_router, prefix="/api")
app.include_router(pcs_router, prefix="/api")
app.include_router(pc_lanes_router, prefix="/api")
app.include_router(risk_register_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(campaign_router, prefix="/api")


class SessionNoteRequest(BaseModel):
    memory: str = ""
    scenes: list[str] = []
    npcs_present: list[str] = []
    clues_discovered: list[str] = []
    threads_touched: list[str] = []
    unresolved_questions: list[str] = []
    next_session_hook: str = ""


class SceneRequest(BaseModel):
    title: str
    type: str = ""
    cuttable: bool = False
    purpose: str = ""
    pc_pressure: str = ""
    entry_pressure: str = ""
    exit_condition: str = ""
    cast: list[str] | str = []
    location: str = ""
    clock: str = ""
    core_clue: str = ""
    superior_clue: str = ""
    optional_clue: str = ""
    false_lead: str = ""
    opening_image: str = ""
    sensory_words: str = ""
    interactable_objects: str = ""
    rules_likely: str = ""
    foundry_needs: list[str] | str = []
    replacement_route: str = ""
    if_succeed: str = ""
    if_fail: str = ""
    if_ignore: str = ""
    if_short: str = ""
    notes: str = ""
    pinned_material: list[dict] = []
    thread_ids: list[str] = []


class SaveDraftRequest(BaseModel):
    target_path: str
    confirm: bool = False
    markdown: str | None = None


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


@app.get("/api/capture/session-note/context")
def capture_session_note_context() -> dict[str, Any]:
    return handle(lambda: services.session_note_context())


@app.post("/api/capture/session-note")
def capture_session_note(payload: SessionNoteRequest) -> dict[str, Any]:
    return handle(
        services.draft_session_note,
        payload.memory,
        scenes=payload.scenes,
        npcs_present=payload.npcs_present,
        clues_discovered=payload.clues_discovered,
        threads_touched=payload.threads_touched,
        unresolved_questions=payload.unresolved_questions,
        next_session_hook=payload.next_session_hook,
    )


@app.post("/api/capture/scene")
def capture_scene(payload: SceneRequest) -> dict[str, Any]:
    return handle(services.draft_scene, payload.model_dump())


@app.get("/api/search")
def search(q: str, limit: int = 20, sources: str = "", include_archive: bool = False) -> list[dict[str, str]]:
    selected = [source.strip() for source in sources.split(",") if source.strip()]
    return handle(services.search_vault, q, limit=limit, sources=selected or None, include_archive=include_archive)


@app.get("/api/search/sources")
def search_sources() -> list[dict[str, Any]]:
    return handle(services.search_collections)



@app.post("/api/drafts/{draft_id}/save")
def save_draft(draft_id: str, payload: SaveDraftRequest) -> dict[str, Any]:
    return handle(
        services.save_draft,
        draft_id,
        payload.target_path,
        markdown=payload.markdown,
        confirm=payload.confirm,
    )


@app.post("/api/drafts/{draft_id}/preview")
def preview_draft_save(draft_id: str, payload: SaveDraftRequest) -> dict[str, Any]:
    return handle(services.preview_draft_save, draft_id, payload.target_path, markdown=payload.markdown)


@app.get("/api/threads/files")
def thread_files() -> list[dict]:
    return handle(lambda: services.thread_files(services.find_vault_root()))


@app.get("/api/foundry/status")
def foundry_status() -> dict[str, Any]:
    return handle(lambda: services.foundry_status(services.find_vault_root()))


@app.get("/api/system/enums")
def system_enums() -> dict[str, list[str]]:
    return enum_catalog()


@app.get("/api/files/markdown")
def get_markdown_file(path: str) -> dict[str, str]:
    return handle(services.vault_markdown_file, path)


@app.put("/api/files/markdown")
def put_markdown_file(path: str, payload: MarkdownSaveRequest) -> dict[str, str]:
    return handle(services.save_vault_markdown_file, path, payload.markdown)
