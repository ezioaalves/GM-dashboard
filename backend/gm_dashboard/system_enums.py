from __future__ import annotations

VISIBILITIES = frozenset({"gm", "player", "mixed", "unknown"})

REVIEW_STATUSES = frozenset(
    {"pending", "accepted", "rejected", "merged", "deferred", "conflict", "stale"}
)

DECISION_REVIEW_STATUSES = REVIEW_STATUSES - {"pending", "stale"}

SYNC_JOB_STATUSES = frozenset(
    {"queued", "running", "succeeded", "failed", "blocked", "cancelled"}
)

FRESHNESS_STATES = frozenset(
    {
        "fresh",
        "stale_source_changed",
        "stale_db_newer",
        "missing_source",
        "missing_mirror",
        "conflict",
        "unknown",
    }
)

SOURCE_SURFACES = frozenset(
    {"vault", "postgres", "foundry_test", "foundry_prod", "asset_fs", "rag", "vps", "manual"}
)

GRAPH_ENDPOINT_TYPES = frozenset({"entity", "thread", "session", "scene", "asset"})

RELATIONSHIP_DIRECTIONS = frozenset({"directed", "bidirectional", "undirected"})

RELATIONSHIP_PROVENANCES = frozenset(
    {"wikilink", "mention", "asset_embed", "manual", "foundry_import", "ai_suggestion", "system"}
)

ASSET_MIRROR_STATES = frozenset(
    {
        "not_mirrored",
        "mirrored",
        "stale_mirror",
        "missing_source",
        "missing_mirror",
        "rejected_variant",
        "conflict",
        "failed",
    }
)

SESSION_STATUSES = frozenset({"planned", "ready", "played", "cancelled", "archived"})
LEGACY_SESSION_STATUSES = frozenset({"Planned", "Active", "Played"})

SCENE_PLACEMENTS = frozenset({"ordered", "floating", "backlog"})


def enum_catalog() -> dict[str, list[str]]:
    return {
        "asset_mirror_states": sorted(ASSET_MIRROR_STATES),
        "freshness_states": sorted(FRESHNESS_STATES),
        "graph_endpoint_types": sorted(GRAPH_ENDPOINT_TYPES),
        "relationship_directions": sorted(RELATIONSHIP_DIRECTIONS),
        "relationship_provenances": sorted(RELATIONSHIP_PROVENANCES),
        "review_statuses": sorted(REVIEW_STATUSES),
        "scene_placements": sorted(SCENE_PLACEMENTS),
        "legacy_session_statuses": sorted(LEGACY_SESSION_STATUSES),
        "session_statuses": sorted(SESSION_STATUSES),
        "source_surfaces": sorted(SOURCE_SURFACES),
        "sync_job_statuses": sorted(SYNC_JOB_STATUSES),
        "visibilities": sorted(VISIBILITIES),
    }
