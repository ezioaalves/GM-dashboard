from __future__ import annotations

import html
import json

from .relay_client import RelayError

GM_ONLY_OWNERSHIP = {"default": 0}


def render_scene_journal_html(scene: dict, mirrored_assets: list[dict]) -> str:
    lines = [f"<h1>{html.escape(scene['title'])}</h1>"]
    if scene.get("description"):
        lines.append(f"<p>{html.escape(scene['description'])}</p>")
    if scene.get("purpose"):
        lines.append(f"<p><strong>Purpose:</strong> {html.escape(scene['purpose'])}</p>")
    if scene.get("opening_image"):
        lines.append(f"<p><strong>Opening image:</strong> {html.escape(scene['opening_image'])}</p>")
    if scene.get("sensory_words"):
        lines.append(f"<p><strong>Sensory words:</strong> {html.escape(scene['sensory_words'])}</p>")
    if scene.get("cast"):
        lines.append(f"<p><strong>Cast:</strong> {', '.join(html.escape(item) for item in scene['cast'])}</p>")
    if scene.get("location"):
        lines.append(f"<p><strong>Location:</strong> {', '.join(html.escape(item) for item in scene['location'])}</p>")
    if mirrored_assets:
        lines.append("<h2>Images</h2>")
        for asset in mirrored_assets:
            lines.append(f'<img src="{html.escape(asset["foundry_path"])}" alt="{html.escape(asset.get("title", ""))}">')
    return "\n".join(lines)


def create_journal(client, scene: dict, html: str) -> str:
    payload = {
        "name": scene["title"] or f"Scene {scene['id']}",
        "ownership": GM_ONLY_OWNERSHIP,
        "pages": [{"name": "Scene", "type": "text", "text": {"content": html, "format": 1}}],
    }
    script = f"""
const data = {json.dumps(payload)};
const journal = await JournalEntry.implementation.create(data);
return {{ ok: true, uuid: journal.uuid }};
"""
    result = client.execute_js(script)
    if not result.get("ok"):
        raise RelayError(result.get("error") or "journal creation failed via execute-js")
    return result["uuid"]


def update_journal(client, journal_uuid: str, html: str) -> None:
    script = f"""
const journal = await fromUuid({json.dumps(journal_uuid)});
if (!journal) {{ return {{ ok: false, error: "journal not found" }}; }}
const page = journal.pages.contents[0];
if (page) {{
  await page.update({{ "text.content": {json.dumps(html)} }});
}} else {{
  await journal.createEmbeddedDocuments("JournalEntryPage", [
    {{ name: "Scene", type: "text", text: {{ content: {json.dumps(html)}, format: 1 }} }}
  ]);
}}
await journal.update({{ ownership: {json.dumps(GM_ONLY_OWNERSHIP)} }});
return {{ ok: true, uuid: journal.uuid }};
"""
    result = client.execute_js(script)
    if not result.get("ok"):
        raise RelayError(result.get("error") or "journal update failed via execute-js")
