from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg2.extras

ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def compute_asset_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_rejected_path(rel_path: str) -> bool:
    return any(part.lower() == "rejected" for part in Path(rel_path).parts)


def read_image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
    except ImportError:
        return None, None
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None, None


def scan_assets(vault_root: Path, cur, dry_run: bool = False) -> dict:
    assets_dir = vault_root / "Lore" / "Assets"
    scanned = 0
    new = 0
    changed_on_disk = 0
    missing = 0
    conflicts = 0
    unchanged = 0
    errors = 0
    review_ids: list[str] = []
    seen_paths: set[str] = set()

    if not assets_dir.exists():
        return {
            "scanned": 0, "new": 0, "changed_on_disk": 0, "missing": 0,
            "conflicts": 0, "unchanged": 0, "errors": 0, "review_ids": [],
        }

    for path in sorted(assets_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ASSET_EXTENSIONS:
            continue
        rel_path = str(path.relative_to(vault_root))
        seen_paths.add(rel_path)
        try:
            data = path.read_bytes()
        except OSError:
            errors += 1
            continue
        scanned += 1
        source_hash = compute_asset_hash(data)

        cur.execute(
            "SELECT id, source_hash, freshness_state FROM lore_assets WHERE source_path = %s",
            (rel_path,),
        )
        existing = cur.fetchone()

        if existing is None:
            new += 1
            width, height = read_image_dimensions(path)
            status = "rejected" if is_rejected_path(rel_path) else "current"
            title = path.stem

            cur.execute(
                """
                SELECT source_path FROM lore_assets
                WHERE source_hash = %s AND source_hash != '' AND source_path != %s
                """,
                (source_hash, rel_path),
            )
            duplicate = cur.fetchone()
            conflict_flags: list[str] = []
            duplicate_of = None
            if duplicate:
                conflicts += 1
                conflict_flags = ["duplicate_content"]
                duplicate_of = duplicate["source_path"]

            if dry_run:
                continue

            cur.execute(
                """
                SELECT id FROM sync_reviews
                WHERE review_type = 'asset_import'
                  AND review_status = 'pending'
                  AND proposed_changes -> 'source_path' = %(path)s::jsonb
                """,
                {"path": psycopg2.extras.Json(rel_path)},
            )
            if cur.fetchone():
                continue

            proposed_changes = {
                "source_path": rel_path,
                "source_hash": source_hash,
                "asset_type": "image",
                "status": status,
                "title": title,
                "width": width,
                "height": height,
                "duplicate_of": duplicate_of,
            }
            cur.execute(
                """
                INSERT INTO sync_reviews (
                  review_type, source_surface, target_surface, target_type, target_id,
                  base_version, current_version, proposed_changes, conflict_flags,
                  review_status
                )
                VALUES (
                  'asset_import', 'vault', 'postgres', 'asset', '',
                  '', %(current_version)s, %(proposed_changes)s, %(conflict_flags)s, 'pending'
                )
                RETURNING id
                """,
                {
                    "current_version": source_hash,
                    "proposed_changes": psycopg2.extras.Json(proposed_changes),
                    "conflict_flags": psycopg2.extras.Json(conflict_flags),
                },
            )
            review_ids.append(str(cur.fetchone()["id"]))
            continue

        if existing["source_hash"] == source_hash:
            unchanged += 1
            if not dry_run and existing["freshness_state"] != "fresh":
                cur.execute(
                    """
                    UPDATE lore_assets
                    SET freshness_state = 'fresh', last_checked_at = now()
                    WHERE id = %s
                    """,
                    (existing["id"],),
                )
            continue

        changed_on_disk += 1
        if not dry_run:
            cur.execute(
                """
                UPDATE lore_assets
                SET freshness_state = 'stale_source_changed', last_checked_at = now()
                WHERE id = %s
                """,
                (existing["id"],),
            )

    cur.execute("SELECT id, source_path FROM lore_assets")
    for row in cur.fetchall():
        if row["source_path"] in seen_paths:
            continue
        missing += 1
        if not dry_run:
            cur.execute(
                """
                UPDATE lore_assets
                SET freshness_state = 'missing_source', last_checked_at = now()
                WHERE id = %s
                """,
                (row["id"],),
            )

    return {
        "scanned": scanned,
        "new": new,
        "changed_on_disk": changed_on_disk,
        "missing": missing,
        "conflicts": conflicts,
        "unchanged": unchanged,
        "errors": errors,
        "review_ids": review_ids,
    }
