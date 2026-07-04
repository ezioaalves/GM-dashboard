from __future__ import annotations

import hashlib
import re
from pathlib import Path

import psycopg2.extras

TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")

ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

ENTITY_TYPE_PREFIXES = [
    ("Lore/NPCs/", "npc"),
    ("Lore/Player_Characters/", "pc"),
    ("Lore/World_of_Rokugan/Locations/", "location"),
    ("Lore/World_of_Rokugan/Kanigakure/", "location"),
    ("Lore/World_of_Rokugan/Great_Nations/", "faction"),
]


def compute_source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    slug = SLUG_STRIP_RE.sub("-", value.lower()).strip("-")
    return slug or "entity"


def parse_title(text: str, path: Path) -> str:
    match = TITLE_RE.search(text)
    if match:
        return match.group(1)
    return path.stem


def classify_entity_type(rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/")
    for prefix, entity_type in ENTITY_TYPE_PREFIXES:
        if normalized.startswith(prefix):
            return entity_type
    return "article"


def parse_sections(text: str) -> list[dict]:
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            headings.append((i, len(match.group(1)), match.group(2)))

    if headings and headings[0][1] == 1:
        body_headings = headings[1:]
    else:
        body_headings = headings

    sections: list[dict] = []
    stack: list[tuple[int, str]] = []
    for idx, (line_no, level, heading_text) in enumerate(body_headings):
        start_line = line_no + 1
        end_line = body_headings[idx + 1][0] if idx + 1 < len(body_headings) else len(lines)
        body = "\n".join(lines[line_no + 1 : end_line]).strip()

        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, heading_text))

        sections.append(
            {
                "heading": heading_text,
                "body": body,
                "section_order": idx,
                "heading_path": [h for _, h in stack],
                "start_line": start_line,
                "end_line": end_line,
            }
        )
    return sections


def extract_wikilinks(text: str) -> list[dict]:
    links: list[dict] = []
    for match in WIKILINK_RE.finditer(text):
        is_embed = match.group(1) == "!"
        inner = match.group(2).replace(r"\|", "|")
        target = inner.split("|", 1)[0]
        target = target.split("^", 1)[0]
        if "#" in target:
            target = target.split("#", 1)[0]
        target = target.strip()
        if not target:
            continue
        links.append({"target": target, "is_embed": is_embed})
    return links


def is_scannable(path: Path, vault_root: Path) -> bool:
    rel = path.relative_to(vault_root)
    if any(part == "_drafts" for part in rel.parts):
        return False
    if path.name.startswith("_"):
        return False
    return True


def looks_like_asset(target: str) -> bool:
    return Path(target).suffix.lower() in ASSET_EXTENSIONS


def parse_source_file(rel_path: str, text: str) -> dict:
    title = parse_title(text, Path(rel_path))
    return {
        "title": title,
        "slug": slugify(title),
        "entity_type": classify_entity_type(rel_path),
        "sections": parse_sections(text),
        "links": extract_wikilinks(text),
    }


def build_relationships(links: list[dict], resolve) -> list[dict]:
    relationships: list[dict] = []
    for link in links:
        target = link["target"]
        if link["is_embed"] and looks_like_asset(target):
            relationships.append(
                {
                    "source_type": "entity",
                    "target_type": "asset",
                    "relationship_type": "embeds",
                    "provenance": "asset_embed",
                    "unresolved_target": target,
                }
            )
            continue

        resolved = resolve(target)
        if resolved:
            relationships.append(
                {
                    "source_type": "entity",
                    "target_type": "entity",
                    "relationship_type": "mentions",
                    "provenance": "wikilink",
                    "target_id": resolved["graph_endpoint_id"],
                }
            )
        else:
            relationships.append(
                {
                    "source_type": "entity",
                    "target_type": "entity",
                    "relationship_type": "mentions",
                    "provenance": "wikilink",
                    "unresolved_target": target,
                }
            )
    return relationships


def diff_sections(existing: list[dict], parsed: list[dict]) -> dict:
    existing_by_path = {tuple(s["heading_path"]): s for s in existing}
    parsed_by_path = {tuple(s["heading_path"]): s for s in parsed}

    added = [s for path, s in parsed_by_path.items() if path not in existing_by_path]
    removed = [s["heading"] for path, s in existing_by_path.items() if path not in parsed_by_path]
    modified = [
        parsed_by_path[path]
        for path in existing_by_path.keys() & parsed_by_path.keys()
        if existing_by_path[path]["body"] != parsed_by_path[path]["body"]
    ]
    return {"added": added, "removed": removed, "modified": modified}


def _resolve_entity(cur, target: str) -> dict | None:
    cur.execute(
        """
        SELECT id, graph_endpoint_id FROM lore_entities
        WHERE lower(slug) = lower(%(t)s) OR lower(title) = lower(%(t)s)
        UNION
        SELECT e.id, e.graph_endpoint_id FROM lore_entities e
        JOIN lore_aliases a ON a.entity_id = e.id
        WHERE lower(a.alias) = lower(%(t)s)
        LIMIT 1
        """,
        {"t": target},
    )
    row = cur.fetchone()
    return dict(row) if row else None


def scan_vault(vault_root: Path, cur, dry_run: bool = False) -> dict:
    lore_dir = vault_root / "Lore"
    scanned = 0
    new = 0
    changed = 0
    unchanged = 0
    errors = 0
    review_ids: list[str] = []

    if not lore_dir.exists():
        return {"scanned": 0, "new": 0, "changed": 0, "unchanged": 0, "errors": 0, "review_ids": []}

    for path in sorted(lore_dir.rglob("*.md")):
        if not is_scannable(path, vault_root):
            continue
        rel_path = str(path.relative_to(vault_root))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            errors += 1
            continue
        scanned += 1
        source_hash = compute_source_hash(text)

        cur.execute(
            "SELECT id, source_hash FROM lore_sources WHERE source_surface = 'vault' AND source_path = %s",
            (rel_path,),
        )
        existing_source = cur.fetchone()

        if existing_source and existing_source["source_hash"] == source_hash:
            unchanged += 1
            continue

        parsed = parse_source_file(rel_path, text)

        cur.execute(
            "SELECT id, graph_endpoint_id FROM lore_entities WHERE slug = %s",
            (parsed["slug"],),
        )
        existing_entity = cur.fetchone()

        existing_sections: list[dict] = []
        if existing_entity:
            cur.execute(
                "SELECT heading, body, heading_path FROM lore_sections WHERE entity_id = %s",
                (existing_entity["id"],),
            )
            existing_sections = [dict(row) for row in cur.fetchall()]

        relationships = build_relationships(
            parsed["links"], lambda target: _resolve_entity(cur, target)
        )

        diff_kind = "changed" if existing_source else "new"
        if diff_kind == "new":
            new += 1
        else:
            changed += 1

        proposed_changes = {
            "diff_kind": diff_kind,
            "entity": {
                "slug": parsed["slug"],
                "title": parsed["title"],
                "entity_type": parsed["entity_type"],
            },
            "sections": parsed["sections"],
            "relationships": relationships,
        }
        if diff_kind == "changed":
            proposed_changes["section_diff"] = diff_sections(existing_sections, parsed["sections"])

        if dry_run:
            continue

        cur.execute(
            """
            SELECT id FROM sync_reviews
            WHERE review_type = 'vault_import'
              AND review_status = 'pending'
              AND proposed_changes -> 'source_paths' = %(paths)s::jsonb
            """,
            {"paths": psycopg2.extras.Json([rel_path])},
        )
        if cur.fetchone():
            continue

        target_id = existing_entity["graph_endpoint_id"] if existing_entity else ""
        cur.execute(
            """
            INSERT INTO sync_reviews (
              review_type, source_surface, target_surface, target_type, target_id,
              base_version, current_version, proposed_changes, review_status
            )
            VALUES (
              'vault_import', 'vault', 'postgres', 'entity', %(target_id)s,
              %(base_version)s, %(current_version)s, %(proposed_changes)s, 'pending'
            )
            RETURNING id
            """,
            {
                "target_id": target_id,
                "base_version": existing_source["source_hash"] if existing_source else "",
                "current_version": source_hash,
                "proposed_changes": psycopg2.extras.Json(
                    {**proposed_changes, "source_paths": [rel_path], "metadata": {}}
                ),
            },
        )
        review_ids.append(str(cur.fetchone()["id"]))

    return {
        "scanned": scanned,
        "new": new,
        "changed": changed,
        "unchanged": unchanged,
        "errors": errors,
        "review_ids": review_ids,
    }
