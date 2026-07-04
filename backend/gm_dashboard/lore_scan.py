from __future__ import annotations

import hashlib
import re
from pathlib import Path

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
