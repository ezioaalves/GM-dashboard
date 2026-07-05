from __future__ import annotations

from pathlib import Path

import psycopg2.extras
import yaml

from . import services

ENTITY_TYPE_TABLES = {"npc": "npcs", "pc": "pcs"}
STATS_KEYS = ("abilities", "classes", "race", "naruto_stats", "chakra", "skills")


def _sync_sheets(vault_root: Path, cur, entity_type: str) -> dict:
    table = ENTITY_TYPE_TABLES[entity_type]
    scanned = 0
    synced = 0
    errors: list[dict] = []

    cur.execute(
        """
        SELECT id, slug, title, source_path FROM lore_entities
        WHERE entity_type = %s AND review_status = 'accepted'
        ORDER BY slug
        """,
        (entity_type,),
    )
    entities = cur.fetchall()

    for entity in entities:
        scanned += 1
        sheet_path = vault_root / entity["source_path"]
        try:
            frontmatter, _ = services.read_markdown(sheet_path)
        except (OSError, services.VaultError, yaml.YAMLError) as exc:
            errors.append({"vault_path": entity["source_path"], "error": str(exc)})
            continue

        name = frontmatter.get("name") or entity["title"]
        img_path = frontmatter.get("img") or None
        stats = {key: frontmatter[key] for key in STATS_KEYS if key in frontmatter}
        foundry_actor_id_test = frontmatter.get("foundry_actor_id_test") or None
        foundry_actor_id_prod = frontmatter.get("foundry_actor_id_prod") or None

        cur.execute(
            f"""
            INSERT INTO {table} (
              slug, name, img_path, vault_path, lore_entity_id, stats,
              foundry_actor_id_test, foundry_actor_id_prod
            )
            VALUES (
              %(slug)s, %(name)s, %(img_path)s, %(vault_path)s, %(lore_entity_id)s, %(stats)s,
              %(foundry_actor_id_test)s, %(foundry_actor_id_prod)s
            )
            ON CONFLICT (slug) DO UPDATE SET
              name = EXCLUDED.name,
              img_path = EXCLUDED.img_path,
              vault_path = EXCLUDED.vault_path,
              lore_entity_id = EXCLUDED.lore_entity_id,
              stats = EXCLUDED.stats,
              foundry_actor_id_test = COALESCE(EXCLUDED.foundry_actor_id_test, {table}.foundry_actor_id_test),
              foundry_actor_id_prod = COALESCE(EXCLUDED.foundry_actor_id_prod, {table}.foundry_actor_id_prod),
              updated_at = now()
            """,
            {
                "slug": entity["slug"],
                "name": name,
                "img_path": img_path,
                "vault_path": entity["source_path"],
                "lore_entity_id": entity["id"],
                "stats": psycopg2.extras.Json(stats),
                "foundry_actor_id_test": foundry_actor_id_test,
                "foundry_actor_id_prod": foundry_actor_id_prod,
            },
        )
        synced += 1

    return {"scanned": scanned, "synced": synced, "errors": errors}


def sync_npc_sheets(vault_root: Path, cur) -> dict:
    return _sync_sheets(vault_root, cur, "npc")


def sync_pc_sheets(vault_root: Path, cur) -> dict:
    return _sync_sheets(vault_root, cur, "pc")
