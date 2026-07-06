from __future__ import annotations

import difflib
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


SESSION_LOGS = Path("Campaign Management/session-logs")
LIVE_PREP = Path("Campaign Management/01 - Live/Next_Session.md")
ARC_CALENDAR = Path("Campaign Management/01 - Live/Current Arc/The Training Arc/Arc Calendar.md")
OP_DASHBOARD = Path("Campaign Management/operational/operational-dashboard.md")
OP_DB = Path("Campaign Management/operational/operational.db")
TICKETS = Path("Campaign Management/operational/tickets")
RAG_DB = Path("Creation Zone/automation_scripts/rag.db")
FOUNDRY_ENV = Path("Creation Zone/automation_scripts/foundry/.env")


class VaultError(Exception):
    pass


def find_vault_root(start: Path | None = None) -> Path:
    env = os.environ.get("KAIHOU_VAULT_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    here = (start or Path(__file__)).resolve()
    for path in [here, *here.parents]:
        if (path / "Campaign Management").exists() and (path / "Creation Zone").exists():
            return path
    raise VaultError(f"could not locate Kaihou vault root from {here}")


def split_frontmatter(text: str, source: Path) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        raise VaultError(f"{source}: no closing frontmatter marker")
    fm = yaml.safe_load(text[4:end]) or {}
    if not isinstance(fm, dict):
        raise VaultError(f"{source}: frontmatter is not a mapping")
    return fm, text[end + 4 :].lstrip("\n")


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    return split_frontmatter(path.read_text(), path)


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def latest_session_log(vault: Path) -> dict[str, Any]:
    logs = []
    for path in (vault / SESSION_LOGS).glob("*.md"):
        if path.name.endswith(".secret.md") or "_drafts" in path.parts:
            continue
        fm, body = read_markdown(path)
        session = fm.get("session")
        if isinstance(session, int):
            logs.append((session, path, fm, body))
    if not logs:
        raise VaultError("no session logs found")
    session, path, fm, body = max(logs, key=lambda row: row[0])
    return {
        "session": session,
        "title": fm.get("title", path.stem),
        "date": str(fm.get("date", "")),
        "path": relative(vault, path),
        "body": body,
        "summary": extract_section(body, "What happened"),
        "notable_moments": bullets_from_section(body, "Notable moments"),
        "npcs_present": fm.get("npcs_present", []),
        "locations": fm.get("locations", []),
        "threads": fm.get("threads", {}),
        "has_secret": path.with_suffix(".secret.md").exists() or bool(fm.get("has_secret")),
    }


def extract_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+", body[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(body)
    return body[match.end() : end].strip()


def bullets_from_section(body: str, heading: str) -> list[str]:
    section = extract_section(body, heading)
    return [line[2:].strip() for line in section.splitlines() if line.startswith("- ")]


def file_status(vault: Path, rel_path: Path, *, stale_after_days: int = 7) -> dict[str, Any]:
    path = vault / rel_path
    if not path.exists():
        return {"name": rel_path.name, "path": rel_path.as_posix(), "state": "missing", "updated_at": None}
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    age_days = (datetime.now(UTC) - mtime).days
    state = "fresh" if age_days <= stale_after_days else "stale"
    return {
        "name": rel_path.name,
        "path": rel_path.as_posix(),
        "state": state,
        "updated_at": mtime.isoformat(),
        "age_days": age_days,
    }


def sqlite_status(vault: Path, rel_path: Path, *, expected_table: str | None = None) -> dict[str, Any]:
    status = file_status(vault, rel_path)
    path = vault / rel_path
    if status["state"] == "missing" or expected_table is None:
        return status
    try:
        con = sqlite3.connect(path)
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (expected_table,)
        ).fetchone()
        con.close()
    except sqlite3.Error as exc:
        status["state"] = "error"
        status["detail"] = str(exc)
        return status
    if row is None:
        status["state"] = "error"
        status["detail"] = f"missing table {expected_table}"
    return status


def freshness(vault: Path) -> dict[str, Any]:
    latest = latest_session_log(vault)
    latest_status = file_status(vault, Path(latest["path"]), stale_after_days=14)
    latest_status["session"] = latest["session"]
    latest_status["title"] = latest["title"]
    return {
        "latest_log": latest_status,
        "arc_cursor": file_status(vault, ARC_CALENDAR, stale_after_days=7),
        "operational_dashboard": file_status(vault, OP_DASHBOARD, stale_after_days=2),
        "operational_db": sqlite_status(vault, OP_DB, expected_table="tickets"),
        "rag_index": sqlite_status(vault, RAG_DB),
        "foundry": foundry_status(vault),
    }


def foundry_status(vault: Path) -> dict[str, Any]:
    env_path = vault / FOUNDRY_ENV
    if not env_path.exists():
        return {"state": "unconfigured", "path": FOUNDRY_ENV.as_posix()}
    configured = []
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            configured.append(line.split("=", 1)[0])
    return {
        "state": "configured" if configured else "unconfigured",
        "path": FOUNDRY_ENV.as_posix(),
        "detail": "Credentials are local only; connection checks stay explicit.",
    }


def session_note_context(vault: Path | None = None) -> dict[str, Any]:
    root = vault or find_vault_root()
    try:
        latest = latest_session_log(root)
    except VaultError:
        latest = None

    live_prep_path = root / LIVE_PREP
    try:
        live_prep_excerpt = live_prep_path.read_text()[:2000] if live_prep_path.exists() else ""
    except Exception:
        live_prep_excerpt = ""

    threads_dir = root / "Campaign Management" / "authorial" / "threads"
    active_threads: list[dict[str, str]] = []
    if threads_dir.exists():
        for path in sorted(threads_dir.glob("*.md")):
            if "_drafts" in path.parts:
                continue
            try:
                fm, _ = read_markdown(path)
            except Exception:
                continue
            if fm.get("status") == "active":
                active_threads.append({
                    "id": str(fm.get("id", path.stem)),
                    "title": str(fm.get("title", path.stem)),
                    "status": str(fm.get("status", "")),
                    "next_move": str(fm.get("next_move", "")),
                })

    npc_list: list[str] = (latest.get("npcs_present") or []) if latest else []
    return {
        "latest_session": latest,
        "live_prep_excerpt": live_prep_excerpt,
        "active_threads": active_threads,
        "npc_list": npc_list,
    }


def ticket_files(vault: Path) -> list[dict[str, Any]]:
    out = []
    for path in sorted((vault / TICKETS).glob("*.md")):
        if "_drafts" in path.parts:
            continue
        fm, body = read_markdown(path)
        stage = fm.get("stage") or default_stage(fm.get("status"))
        out.append({
            "id": fm.get("id", path.stem),
            "title": fm.get("title", path.stem),
            "status": fm.get("status", "open"),
            "stage": stage,
            "next_action": fm.get("next_action", ""),
            "resume_note": fm.get("resume_note", ""),
            "review_after": str(fm.get("review_after", "")) if fm.get("review_after") else "",
            "area": fm.get("area", ""),
            "priority": fm.get("priority", "med"),
            "path": relative(vault, path),
            "body_excerpt": first_paragraph(body),
        })
    return out


def default_stage(status: str | None) -> str:
    if status == "in_progress":
        return "now"
    if status in {"done", "dropped"}:
        return "done"
    if status == "blocked":
        return "deferred"
    return "next"


def first_paragraph(body: str) -> str:
    paragraphs = [p.strip().replace("\n", " ") for p in body.split("\n\n") if p.strip()]
    return paragraphs[1] if paragraphs and paragraphs[0].startswith("#") and len(paragraphs) > 1 else (paragraphs[0] if paragraphs else "")


THREADS = Path("Campaign Management/authorial/threads")


def thread_files(vault: Path) -> list[dict[str, Any]]:
    threads_dir = vault / THREADS
    if not threads_dir.exists():
        return []
    result = []
    for path in sorted(threads_dir.glob("*.md")):
        if "_drafts" in path.parts or path.name.startswith("_"):
            continue
        try:
            fm, _ = read_markdown(path)
            result.append({
                "id": fm.get("id", path.stem),
                "title": fm.get("title", path.stem),
                "status": fm.get("status", "active"),
            })
        except Exception:
            pass
    return result


def cockpit_session(vault: Path | None = None) -> dict[str, Any]:
    root = vault or find_vault_root()
    latest = latest_session_log(root)
    tickets = ticket_files(root)
    active = [t for t in tickets if t["status"] in {"open", "in_progress", "blocked"}]
    columns = {
        "now": [
            {
                "id": "session-17-cliffhanger",
                "title": "Ox 22 cliffhanger",
                "detail": "Party is fleeing the Tetsu no Oni in hostile forest; Haiiro is missing.",
                "source": latest["path"],
            }
        ],
        "next": [
            t for t in active
            if t["stage"] == "next" and t["id"] != "complete-vault-housekeeping-cleanup"
        ][:8],
        "scene_deck": [
            {
                "id": "survive-the-forest",
                "title": "Survive the forest",
                "purpose": "Turn the retreat into choices: route, rescue Haiiro, or signal patrol support.",
                "cast": ["Dan", "Ikazuchi", "Suigin", "Kaguya_Haiiro", "Tetsu no Oni"],
                "clock": "Shadowlands escalation",
                "foundry_needs": ["forest chase map", "Tetsu no Oni token", "aberration remnants"],
            }
        ],
        "capture": [
            {
                "id": "quick-session-note",
                "title": "Quick Session Note",
                "detail": "Use memory plus stale prep to draft a canonical session log.",
            },
            {
                "id": "quick-scene",
                "title": "Quick Scene",
                "detail": "Capture purpose, cast, clue, thread/clock, and Foundry needs.",
            },
        ],
        "follow_up": [
            t for t in active
            if t["stage"] in {"now", "deferred"} or "webapp" in t["id"]
        ][:8],
    }
    return {
        "latest_session": latest,
        "leave_off": columns["now"][0],
        "columns": columns,
    }


def search_vault(q: str, vault: Path | None = None, *, limit: int = 20) -> list[dict[str, str]]:
    root = vault or find_vault_root()
    needle = q.lower().strip()
    if not needle:
        return []
    matches = []
    for base in ["Campaign Management", "Lore", "Mechanics"]:
        for path in (root / base).rglob("*.md"):
            if ".git" in path.parts or "_drafts" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            idx = text.lower().find(needle)
            if idx == -1:
                continue
            start = max(0, idx - 80)
            end = min(len(text), idx + len(q) + 120)
            matches.append({
                "path": relative(root, path),
                "title": path.stem.replace("_", " "),
                "snippet": " ".join(text[start:end].split()),
            })
            if len(matches) >= limit:
                return matches
    return matches


def vault_markdown_file(path: str, vault: Path | None = None) -> dict[str, str]:
    root = vault or find_vault_root()
    target = resolve_vault_markdown(root, path)
    text = target.read_text()
    return {"path": relative(root, target), "markdown": text}


def save_vault_markdown_file(path: str, markdown: str, vault: Path | None = None) -> dict[str, str]:
    root = vault or find_vault_root()
    target = resolve_vault_markdown(root, path)
    old = target.read_text() if target.exists() else ""
    target.write_text(markdown)
    return {
        "path": relative(root, target),
        "diff": unified_diff(old, markdown, fromfile=path, tofile=path),
    }


def resolve_canonical_markdown_target(root: Path, path: str) -> Path:
    if not path:
        raise VaultError("missing canonical target path")
    target = (root / path).resolve()
    if root.resolve() not in [target, *target.parents]:
        raise VaultError("target path escapes vault")
    if target.suffix != ".md":
        raise VaultError("only Markdown files can be saved canonically")
    if "_drafts" in target.parts:
        raise VaultError("canonical target cannot be inside _drafts")
    allowed_roots = [
        root / "Campaign Management",
        root / "Lore",
        root / "Mechanics",
    ]
    if not any(base.resolve() in [target, *target.parents] for base in allowed_roots):
        raise VaultError("target path is outside canonical vault content roots")
    return target


def resolve_vault_markdown(root: Path, path: str) -> Path:
    if not path:
        raise VaultError("missing markdown path")
    target = (root / path).resolve()
    if root.resolve() not in [target, *target.parents]:
        raise VaultError("path escapes vault")
    if target.suffix != ".md":
        raise VaultError("only Markdown files can be opened here")
    allowed_roots = [
        root / "Campaign Management",
        root / "Lore",
        root / "Mechanics",
    ]
    if not any(base.resolve() in [target, *target.parents] for base in allowed_roots):
        raise VaultError("path is outside editable vault content roots")
    if "_drafts" in target.parts or target.exists():
        return target
    raise VaultError(f"markdown file does not exist: {path}")


def _render_list(items: list[str], todo_msg: str) -> str:
    if not items:
        return f"<!-- TODO: {todo_msg} -->"
    return "\n".join(f"- {item}" for item in items)


def _render_numbered(items: list[str], todo_msg: str) -> str:
    if not items:
        return f"<!-- TODO: {todo_msg} -->"
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def _yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(items) + "]"


def _derive_title_structured(next_session_hook: str, scenes: list[str], memory: str) -> str:
    if next_session_hook.strip():
        return next_session_hook.strip()[:80]
    if scenes:
        return scenes[0].strip()[:80]
    return derive_title(memory)


def draft_session_note(
    memory: str = "",
    vault: Path | None = None,
    *,
    scenes: list[str] | None = None,
    npcs_present: list[str] | None = None,
    clues_discovered: list[str] | None = None,
    threads_touched: list[str] | None = None,
    unresolved_questions: list[str] | None = None,
    next_session_hook: str = "",
) -> dict[str, Any]:
    root = vault or find_vault_root()
    latest = latest_session_log(root)
    next_session = (root / LIVE_PREP).read_text() if (root / LIVE_PREP).exists() else ""
    session_no = int(latest["session"]) + 1
    today = datetime.now().date().isoformat()

    _scenes = scenes or []
    _npcs = npcs_present or []
    _clues = clues_discovered or []
    _threads = threads_touched or []
    _questions = unresolved_questions or []

    title = _derive_title_structured(next_session_hook, _scenes, memory) or f"Session {session_no} Draft"
    safe_title = title.replace('"', '\\"')

    markdown = f"""---
schema_version: 1
session: {session_no}
date: {today}
title: "{safe_title}"
poles_advanced: []
threads:
  advanced: []
  planted: []
  resolved: []
npcs_present: {_yaml_list(_npcs)}
locations: []
has_secret: false
---

# Session {session_no} — {title}

## What happened

{_render_numbered(_scenes, "add scene summaries, one per line")}

## NPCs in play

{_render_list(_npcs, "list NPCs present")}

## Clues discovered

{_render_list(_clues, "list clues discovered")}

## Threads touched

{_render_list(_threads, "list threads/clocks touched")}

## Unresolved questions

{_render_list(_questions, "list unresolved questions")}

## Hook for next session

{next_session_hook.strip() if next_session_hook.strip() else "<!-- TODO: set next-session hook -->"}

## Continuity notes

{memory.strip() if memory.strip() else "<!-- TODO: add GM continuity notes -->"}

## Notable moments

<!-- TODO: add table moments -->
"""
    draft_id = f"session-{session_no}-{uuid.uuid4().hex[:8]}"
    path = root / SESSION_LOGS / "_drafts" / f"{draft_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown)
    return {
        "id": draft_id,
        "type": "session-log",
        "path": relative(root, path),
        "default_target_path": f"{SESSION_LOGS.as_posix()}/{session_no:02d}-{slugify(title)}.md",
        "markdown": markdown,
        "source": {
            "latest_session": latest,
            "live_prep_excerpt": next_session[:2000],
        },
        "diff": unified_diff("", markdown, fromfile="/dev/null", tofile=relative(root, path)),
    }


def derive_title(memory: str) -> str:
    for line in memory.splitlines():
        clean = line.strip().strip("# ")
        if clean:
            return clean[:80]
    return ""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "draft"


def draft_scene(payload: dict[str, Any], vault: Path | None = None) -> dict[str, Any]:
    root = vault or find_vault_root()
    draft_id = f"scene-{uuid.uuid4().hex[:8]}"
    title = payload.get("title") or "Untitled Scene"

    # Extract all fields from payload
    scene_type = payload.get("type", "")
    cuttable = payload.get("cuttable", False)
    purpose = payload.get("purpose", "")
    pc_pressure = payload.get("pc_pressure", "")
    entry_pressure = payload.get("entry_pressure", "")
    exit_condition = payload.get("exit_condition", "")
    cast_list = payload.get("cast", "")
    if isinstance(cast_list, list):
        cast_list = ", ".join(cast_list)
    location = payload.get("location", "")
    clock_thread = payload.get("clock", "")
    core_clue = payload.get("core_clue", "")
    superior_clue = payload.get("superior_clue", "")
    optional_clue = payload.get("optional_clue", "")
    false_lead = payload.get("false_lead", "")
    opening_image = payload.get("opening_image", "")
    sensory_words = payload.get("sensory_words", "")
    interactable_objects = payload.get("interactable_objects", "")
    rules_likely = payload.get("rules_likely", "")
    foundry_needs = payload.get("foundry_needs", "")
    if isinstance(foundry_needs, list):
        foundry_needs = ", ".join(foundry_needs)
    replacement_route = payload.get("replacement_route", "")
    if_succeed = payload.get("if_succeed", "")
    if_fail = payload.get("if_fail", "")
    if_ignore = payload.get("if_ignore", "")
    if_short = payload.get("if_short", "")
    notes = payload.get("notes", "")
    pinned_material = payload.get("pinned_material", [])
    thread_ids = payload.get("thread_ids", [])

    # Build Scene Card markdown (only include non-empty fields)
    md_lines = [f"## Scene: {title}\n"]

    # Scene metadata section
    if scene_type:
        md_lines.append(f"Type: {scene_type}")
    if purpose:
        md_lines.append(f"Purpose: {purpose}")
    if pc_pressure:
        md_lines.append(f"PC pressure: {pc_pressure}")
    if clock_thread:
        md_lines.append(f"Clock or thread: {clock_thread}")
    if location:
        md_lines.append(f"Location: {location}")
    if cast_list:
        md_lines.append(f"Cast: {cast_list}")
    if cuttable:
        md_lines.append("Cuttable: yes")

    md_lines.append("")  # blank line separator

    # Entry/exit section
    if entry_pressure:
        md_lines.append(f"Entry pressure: {entry_pressure}")
    if exit_condition:
        md_lines.append(f"Exit condition: {exit_condition}")

    md_lines.append("")

    # Sensory prep section
    if opening_image:
        md_lines.append(f"Opening image: {opening_image}")
    if interactable_objects:
        md_lines.append(f"Interactable objects: {interactable_objects}")
    if sensory_words:
        md_lines.append(f"Sensory words: {sensory_words}")
    if rules_likely:
        md_lines.append(f"Rules likely: {rules_likely}")

    md_lines.append("")

    # Clue structure section
    if core_clue:
        md_lines.append(f"Core information: {core_clue}")
    if superior_clue:
        md_lines.append(f"Superior information: {superior_clue}")
    if optional_clue:
        md_lines.append(f"Optional information: {optional_clue}")
    if false_lead:
        md_lines.append(f"False lead risk: {false_lead}")

    md_lines.append("")

    # Contingencies section
    if if_succeed:
        md_lines.append(f"If PCs succeed: {if_succeed}")
    if if_fail:
        md_lines.append(f"If PCs fail: {if_fail}")
    if if_ignore:
        md_lines.append(f"If PCs ignore it: {if_ignore}")
    if if_short:
        md_lines.append(f"If time is short: {if_short}")
    if replacement_route:
        md_lines.append(f"Replacement route: {replacement_route}")

    md_lines.append("")

    # Foundry needs
    if foundry_needs:
        md_lines.append(f"Foundry needs: {foundry_needs}")

    # Notes section
    if notes:
        md_lines.append("\n## Notes\n")
        md_lines.append(notes)

    # Attached material section
    if pinned_material:
        md_lines.append("\n## Attached Material\n")
        for item in pinned_material:
            title_pin = item.get("title", "")
            path_pin = item.get("path", "")
            if path_pin:
                md_lines.append(f"- [[{title_pin}]] — `{path_pin}`")
            elif title_pin:
                md_lines.append(f"- {title_pin}")

    markdown = "\n".join(md_lines)

    # Write markdown file
    path = root / "Campaign Management" / "01 - Live" / "Current Situation" / "_drafts" / f"{draft_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown)

    return {
        "id": draft_id,
        "type": "scene",
        "path": relative(root, path),
        "default_target_path": (
            "Campaign Management/01 - Live/Current Situation/"
            f"{slugify(title)}.md"
        ),
        "markdown": markdown,
    }


def find_draft(root: Path, draft_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", draft_id):
        raise VaultError(f"invalid draft id: {draft_id}")
    candidates = list(root.glob(f"**/_drafts/{draft_id}.md"))
    if not candidates:
        raise VaultError(f"draft not found: {draft_id}")
    return candidates[0]


def preview_draft_save(
    draft_id: str,
    target_path: str,
    vault: Path | None = None,
    *,
    markdown: str | None = None,
) -> dict[str, Any]:
    root = vault or find_vault_root()
    draft = find_draft(root, draft_id)
    target = resolve_canonical_markdown_target(root, target_path)
    old = target.read_text() if target.exists() else ""
    new = draft.read_text() if markdown is None else markdown
    return {
        "saved": False,
        "draft_path": relative(root, draft),
        "path": relative(root, target),
        "diff": unified_diff(old, new, fromfile=target_path, tofile=target_path),
        "markdown": new,
        "target_exists": target.exists(),
    }


def save_draft(
    draft_id: str,
    target_path: str,
    vault: Path | None = None,
    *,
    markdown: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        raise VaultError("canonical save requires confirm=true after preview")
    root = vault or find_vault_root()
    draft = find_draft(root, draft_id)
    preview = preview_draft_save(draft_id, target_path, root, markdown=markdown)
    target = resolve_canonical_markdown_target(root, preview["path"])
    if markdown is not None:
        draft.write_text(markdown)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(preview["markdown"])
    return {
        **preview,
        "saved": True,
    }


def unified_diff(old: str, new: str, *, fromfile: str, tofile: str) -> str:
    return "\n".join(difflib.unified_diff(
        old.splitlines(), new.splitlines(), fromfile=fromfile, tofile=tofile, lineterm=""
    ))
