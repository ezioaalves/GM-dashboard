import { useMemo, useRef, useState } from "react";
import { Modal, Field } from "../components/Modal";
import { PillSelect } from "../components/PillSelect";
import type { PageKey } from "../components/Sidebar";
import {
  useLoreEntitiesQuery,
  useLoreEntityDetailQuery,
  useLoreSourcesQuery,
  useCreateLoreEntity,
  usePatchLoreEntity,
  useAddLoreAlias,
  useAddLoreSection,
  usePatchLoreSection,
  useDeleteLoreSection,
  useCreateRelationship,
  type LoreEntity,
  type LoreRelationship,
} from "../api/lore";
import { useScanVault } from "../api/sync";
import { AssetThumb } from "../components/AssetThumb";
import { useNPCsQuery, usePCsQuery } from "../api/npcs";
import {
  usePushNPCToFoundry,
  useRefreshNPCFromFoundry,
  useRefreshPCFromFoundry,
  useSyncNPCsFromVault,
  useSyncPCsFromVault,
} from "../api/foundry";
import type { NPC, PC } from "../types/npc";

const ENTITY_TYPES = ["person", "place", "faction", "article"] as const;

type Selection =
  | { kind: "entity"; id: string }
  | { kind: "npc"; slug: string }
  | { kind: "pc"; slug: string }
  | null;

function FreshnessBadge({ state }: { state: string }) {
  const cls =
    state === "fresh"
      ? "fresh"
      : state === "conflict"
        ? "conflict"
        : state?.startsWith("stale") || state?.startsWith("missing")
          ? "stale"
          : "superseded";
  return (
    <span className={`badge-pill badge-pill--${cls}`}>
      <span className="badge-pill-dot" />
      {(state || "unknown").replace(/_/g, " ").toUpperCase()}
    </span>
  );
}

function relTargetLabel(rel: LoreRelationship, selfId: string): string {
  const other =
    rel.source_id === selfId || rel.source_id.endsWith(selfId) ? rel.target_id : rel.source_id;
  return rel.unresolved_target || other.replace(/^entity:/, "");
}

// ── NPC / PC roster detail blocks ────────────────────────────────────────────

function NpcDetail({ npc, env, toast }: { npc: NPC; env: "test" | "prod"; toast: (m: string) => void }) {
  const push = usePushNPCToFoundry();
  const refresh = useRefreshNPCFromFoundry();
  const [confirmingPush, setConfirmingPush] = useState(false);

  const testId = npc.foundry_actor_id_test;
  const prodId = npc.foundry_actor_id_prod;

  return (
    <div className="library-detail">
      <div className="panel" style={{ gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span className="type-chip type-chip--spotlight">NPC</span>
          <h2 className="drawer-title" style={{ fontSize: 19 }}>
            {npc.name}
          </h2>
          {npc.rank && <span className="chip">{npc.rank}</span>}
          {npc.status && <span className="chip">{npc.status}</span>}
        </div>
        {npc.narrative && <p className="drawer-summary">{npc.narrative}</p>}
        <div className="child-card-grid">
          <div>
            <span className="child-key">ROLE</span>
            <br />
            {npc.role || "—"}
          </div>
          <div>
            <span className="child-key">AFFILIATION</span>
            <br />
            {npc.affiliation || "—"}
          </div>
          <div>
            <span className="child-key">LOCATION</span>
            <br />
            {npc.location || "—"}
          </div>
          <div>
            <span className="child-key">TAGS</span>
            <br />
            {npc.tags.join(", ") || "—"}
          </div>
        </div>
        {npc.gm_secret && (
          <div className="field" style={{ gap: 4, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
            <span className="field-label" style={{ color: "var(--red-bright)" }}>
              GM SECRET
            </span>
            <span className="panel-note">{npc.gm_secret}</span>
          </div>
        )}
      </div>

      <div className="panel" style={{ gap: 14 }}>
        <span className="field-label">NPC — FOUNDRY MIRROR</span>
        <div className="adventure-summary-grid">
          <div className="field" style={{ gap: 6 }}>
            <span className="board-hint">TEST</span>
            <span className={`mono-inline`} style={{ color: testId ? "var(--teal-bright)" : "var(--text-faint)" }}>
              {testId ? "mirrored" : "not mirrored"}
            </span>
          </div>
          <div className="field" style={{ gap: 6 }}>
            <span className="board-hint">PROD</span>
            <span className={`mono-inline`} style={{ color: prodId ? "var(--teal-bright)" : "var(--text-faint)" }}>
              {prodId ? "mirrored" : "not mirrored"}
            </span>
          </div>
        </div>
        <div className="rule-actions" style={{ alignItems: "center" }}>
          <button
            className={npc.foundry_sync_locked ? "btn-ghost" : "btn btn-primary"}
            disabled={npc.foundry_sync_locked || push.isPending}
            onClick={() => setConfirmingPush(true)}
          >
            {npc.foundry_sync_locked ? "Pushed & locked" : `Push to Foundry (${env.toUpperCase()})`}
          </button>
          <button
            className="btn-ghost"
            disabled={refresh.isPending}
            onClick={() =>
              refresh.mutate(
                { slug: npc.slug, env },
                {
                  onSuccess: (res) =>
                    toast(
                      res.changed
                        ? "Stats differ — a pending review was created. Resolve in Sync Center."
                        : "No changes — Foundry matches the roster.",
                    ),
                  onError: (err) => toast(`Refresh failed: ${err.message}`),
                },
              )
            }
          >
            {refresh.isPending ? "Refreshing…" : "Refresh from Foundry"}
          </button>
          <span className="field-hint" style={{ marginLeft: "auto" }}>
            Push is one-time &amp; irreversible · refresh is review-gated
          </span>
        </div>
        {confirmingPush && (
          <div className="push-confirm">
            <span>
              Pushing to Foundry locks this NPC permanently — there is no re-push or update path.
              Continue?
            </span>
            <button className="btn-ghost" style={{ flex: "none" }} onClick={() => setConfirmingPush(false)}>
              Cancel
            </button>
            <button
              className="btn-danger"
              style={{ flex: "none" }}
              disabled={push.isPending}
              onClick={() =>
                push.mutate(
                  { slug: npc.slug, env },
                  {
                    onSuccess: () => {
                      setConfirmingPush(false);
                      toast(`${npc.name} pushed to Foundry ${env.toUpperCase()} and locked`);
                    },
                    onError: (err) => {
                      setConfirmingPush(false);
                      toast(`Push failed: ${err.message}`);
                    },
                  },
                )
              }
            >
              {push.isPending ? "Pushing…" : "Push & lock"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function PcDetail({ pc, env, toast }: { pc: PC; env: "test" | "prod"; toast: (m: string) => void }) {
  const refresh = useRefreshPCFromFoundry();
  return (
    <div className="library-detail">
      <div className="panel" style={{ gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="type-chip type-chip--hard">PC</span>
          <h2 className="drawer-title" style={{ fontSize: 19 }}>
            {pc.name}
          </h2>
          {pc.level != null && <span className="chip">level {pc.level}</span>}
        </div>
        {pc.narrative && <p className="drawer-summary">{pc.narrative}</p>}
        <div className="child-card-grid">
          <div>
            <span className="child-key">PLAYER</span>
            <br />
            {pc.player || "—"}
          </div>
          <div>
            <span className="child-key">CLASSES</span>
            <br />
            {pc.classes?.map((c) => `${c.name} ${c.level}`).join(", ") || "—"}
          </div>
        </div>
      </div>
      <div className="panel" style={{ gap: 14 }}>
        <span className="field-label">PC — READ-ONLY, FOUNDRY IS SOURCE OF TRUTH</span>
        <p className="panel-note">
          PCs are import-only. There is no push path — the roster mirrors Foundry, never the
          reverse.
        </p>
        <div className="rule-actions" style={{ alignItems: "center" }}>
          <button
            className="btn-ghost"
            disabled={refresh.isPending}
            onClick={() =>
              refresh.mutate(
                { slug: pc.slug, env },
                {
                  onSuccess: () => toast(`${pc.name} refreshed from Foundry.`),
                  onError: (err) => toast(`Refresh failed: ${err.message}`),
                },
              )
            }
          >
            {refresh.isPending ? "Refreshing…" : "Refresh from Foundry"}
          </button>
          <span className="field-hint" style={{ marginLeft: "auto" }}>
            Direct write, no review gate
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export function Library({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [mode, setMode] = useState<"entities" | "sources">("entities");
  const [selection, setSelection] = useState<Selection>(null);
  const [relView, setRelView] = useState<"list" | "graph">("list");
  const [env] = useState<"test" | "prod">("test");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: entities = [] } = useLoreEntitiesQuery();
  const { data: sources = [] } = useLoreSourcesQuery();
  const { data: npcs = [] } = useNPCsQuery();
  const { data: pcs = [] } = usePCsQuery();

  const entityDetailId = selection?.kind === "entity" ? selection.id : null;
  const { data: detail } = useLoreEntityDetailQuery(entityDetailId);

  const createEntity = useCreateLoreEntity();
  const patchEntity = usePatchLoreEntity();
  const addAlias = useAddLoreAlias();
  const addSection = useAddLoreSection();
  const patchSection = usePatchLoreSection();
  const deleteSection = useDeleteLoreSection();
  const createRel = useCreateRelationship();
  const scan = useScanVault();
  const syncNpcs = useSyncNPCsFromVault();
  const syncPcs = useSyncPCsFromVault();

  const [modal, setModal] = useState<
    | { kind: "entity"; id: string | null; data: Record<string, string> }
    | { kind: "alias"; data: Record<string, string> }
    | { kind: "section"; id: string | null; data: Record<string, string> }
    | { kind: "relationship"; data: Record<string, string> }
    | null
  >(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4200);
  }

  interface Row {
    key: string;
    kind: "entity" | "npc" | "pc";
    id: string;
    title: string;
    typeLabel: string;
    typeCls: string;
    freshness: string;
  }

  const rows: Row[] = useMemo(() => {
    const entityRows: Row[] = entities.map((e: LoreEntity) => ({
      key: `entity-${e.id}`,
      kind: "entity",
      id: e.id,
      title: e.title,
      typeLabel: e.entity_type.toUpperCase(),
      typeCls:
        e.entity_type === "person"
          ? "soft"
          : e.entity_type === "place"
            ? "added"
            : e.entity_type === "faction"
              ? "replacement"
              : "cut",
      freshness: e.freshness_state,
    }));
    const npcRows: Row[] = npcs.map((n) => ({
      key: `npc-${n.slug}`,
      kind: "npc",
      id: n.slug,
      title: n.name,
      typeLabel: "NPC",
      typeCls: "spotlight",
      freshness: "fresh",
    }));
    const pcRows: Row[] = pcs.map((p) => ({
      key: `pc-${p.slug}`,
      kind: "pc",
      id: p.slug,
      title: p.name,
      typeLabel: "PC",
      typeCls: "hard",
      freshness: "fresh",
    }));
    return [...entityRows, ...npcRows, ...pcRows];
  }, [entities, npcs, pcs]);

  const typeCounts: Record<string, number> = {};
  for (const r of rows) typeCounts[r.typeLabel.toLowerCase()] = (typeCounts[r.typeLabel.toLowerCase()] ?? 0) + 1;

  const filtered = rows.filter(
    (r) => typeFilter === "all" || r.typeLabel.toLowerCase() === typeFilter,
  );

  const selectedNpc = selection?.kind === "npc" ? npcs.find((n) => n.slug === selection.slug) : null;
  const selectedPc = selection?.kind === "pc" ? pcs.find((p) => p.slug === selection.slug) : null;

  function saveModal() {
    if (!modal) return;
    const done = { onSuccess: () => setModal(null) };
    if (modal.kind === "entity") {
      if (modal.id == null) {
        const slug = (modal.data.title || "").trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
        if (!slug) return;
        createEntity.mutate(
          {
            slug,
            title: modal.data.title,
            entity_type: modal.data.entity_type || "article",
            summary: modal.data.summary,
          },
          {
            onSuccess: (created) => {
              setModal(null);
              setSelection({ kind: "entity", id: created.id });
            },
          },
        );
      } else {
        patchEntity.mutate(
          { id: modal.id, title: modal.data.title, summary: modal.data.summary },
          done,
        );
      }
    } else if (modal.kind === "alias" && detail) {
      if (!modal.data.alias?.trim()) return;
      addAlias.mutate({ entityId: detail.id, alias: modal.data.alias.trim() }, done);
    } else if (modal.kind === "section" && detail) {
      if (modal.id == null) {
        const sourceId = modal.data.source_id || detail.source_id || sources[0]?.id;
        if (!sourceId) {
          showToast("Ingest a lore source first — sections must belong to a source");
          return;
        }
        addSection.mutate(
          {
            entityId: detail.id,
            source_id: sourceId,
            heading: modal.data.heading || "",
            body: modal.data.body || "",
            section_order: detail.sections.length,
          },
          done,
        );
      } else {
        patchSection.mutate(
          { id: modal.id, heading: modal.data.heading, body: modal.data.body },
          done,
        );
      }
    } else if (modal.kind === "relationship" && detail) {
      if (!modal.data.target?.trim()) return;
      const target = modal.data.target.trim();
      const match = entities.find((e) => e.title === target || e.slug === target);
      createRel.mutate(
        {
          source_type: "entity",
          source_id: detail.id,
          target_type: "entity",
          target_id: match?.id,
          unresolved_target: match ? "" : target,
          relationship_type: modal.data.relationship_type || "mentions",
          direction: modal.data.direction || "directed",
          provenance: "manual",
        },
        done,
      );
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Library</h1>
          <span className="page-subtitle">lore graph · rosters · sources — cross-phase reference</span>
        </div>
        <div className="header-actions">
          <button
            className="btn-ghost"
            disabled={scan.isPending || syncNpcs.isPending || syncPcs.isPending}
            onClick={() => {
              scan.mutate(undefined, {
                onSuccess: () => showToast("Vault scan finished — proposals staged in Sync Center"),
                onError: (err) => showToast(`Scan failed: ${err.message}`),
              });
              syncNpcs.mutate();
              syncPcs.mutate();
            }}
          >
            {scan.isPending ? "Scanning…" : "Scan vault"}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => setModal({ kind: "entity", id: null, data: { title: "", entity_type: "article", summary: "" } })}
          >
            ＋ New entity
          </button>
        </div>
      </header>

      <div className="board-toolbar">
        <div className="lens-toggle">
          <button
            className={`lens-option${mode === "entities" ? " lens-option--active" : ""}`}
            onClick={() => setMode("entities")}
          >
            Entities
          </button>
          <button
            className={`lens-option${mode === "sources" ? " lens-option--active" : ""}`}
            onClick={() => setMode("sources")}
          >
            Sources
          </button>
        </div>
        {mode === "entities" && (
          <div className="lens-filters" style={{ marginTop: 0 }}>
            {["all", ...ENTITY_TYPES, "npc", "pc"].map((t) => (
              <button
                key={t}
                className={`lens-filter${typeFilter === t ? " lens-filter--active" : ""}`}
                onClick={() => setTypeFilter(t)}
              >
                {t === "all" ? "All" : `${t} ${typeCounts[t] ?? 0}`}
              </button>
            ))}
          </div>
        )}
        <button className="search-box" style={{ marginLeft: "auto", width: 200 }} onClick={() => onNavigate("library-search")}>
          <kbd>⌘K</kbd>
          Search vault…
        </button>
      </div>

      {mode === "entities" ? (
        <div className="library-grid">
          <div className="library-list">
            {filtered.length === 0 && <div className="empty-state">Nothing here yet.</div>}
            {filtered.map((row) => {
              const selected =
                (selection?.kind === "entity" && row.kind === "entity" && selection.id === row.id) ||
                (selection?.kind === "npc" && row.kind === "npc" && selection.slug === row.id) ||
                (selection?.kind === "pc" && row.kind === "pc" && selection.slug === row.id);
              return (
                <button
                  key={row.key}
                  className={`library-row${selected ? " library-row--selected" : ""}`}
                  onClick={() =>
                    setSelection(
                      row.kind === "entity"
                        ? { kind: "entity", id: row.id }
                        : row.kind === "npc"
                          ? { kind: "npc", slug: row.id }
                          : { kind: "pc", slug: row.id },
                    )
                  }
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className={`type-chip type-chip--${row.typeCls}`}>{row.typeLabel}</span>
                    <span className="library-row-title">{row.title}</span>
                  </div>
                  {row.kind === "entity" && <FreshnessBadge state={row.freshness} />}
                </button>
              );
            })}
          </div>

          {selection == null && (
            <div className="empty-state" style={{ padding: 48 }}>
              Select an entity to view its detail.
            </div>
          )}

          {selectedNpc && <NpcDetail npc={selectedNpc} env={env} toast={showToast} />}
          {selectedPc && <PcDetail pc={selectedPc} env={env} toast={showToast} />}

          {selection?.kind === "entity" && detail && (
            <div className="library-detail">
              <div className="panel" style={{ gap: 14 }}>
                <div style={{ display: "flex", gap: 16 }}>
                  {(() => {
                    const portrait =
                      detail.assets.find((a) => a.asset_type === "image" && a.status === "current") ??
                      detail.assets.find((a) => a.asset_type === "image");
                    return portrait ? <AssetThumb asset={portrait} className="entity-portrait" /> : null;
                  })()}
                  <div style={{ flex: 1, display: "grid", gap: 10, alignContent: "start" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <span className="type-chip type-chip--cut">{detail.entity_type.toUpperCase()}</span>
                      <h2 className="drawer-title" style={{ fontSize: 19 }}>
                        {detail.title}
                      </h2>
                      <FreshnessBadge state={detail.freshness_state} />
                      <button
                        className="child-edit"
                        onClick={() =>
                          setModal({
                            kind: "entity",
                            id: detail.id,
                            data: { title: detail.title, summary: detail.summary, entity_type: detail.entity_type },
                          })
                        }
                      >
                        Edit
                      </button>
                    </div>
                    <p className="drawer-summary">{detail.summary || "No summary yet."}</p>
                  </div>
                </div>
                <div className="pin-chip-row" style={{ borderTop: "1px solid var(--border)", paddingTop: 12, alignItems: "center" }}>
                  <span className="field-label" style={{ alignSelf: "center" }}>
                    ALIASES
                  </span>
                  {detail.aliases.map((al) => (
                    <span className="pin-chip" key={al.id}>
                      {al.alias}
                    </span>
                  ))}
                  <button
                    className="board-new-scene"
                    style={{ marginLeft: 0 }}
                    onClick={() => setModal({ kind: "alias", data: { alias: "" } })}
                  >
                    ＋ alias
                  </button>
                </div>
              </div>

              <div className="field" style={{ gap: 10 }}>
                <div className="board-toolbar">
                  <span className="field-label">SECTIONS</span>
                  <button
                    className="board-new-scene"
                    style={{ marginLeft: 0 }}
                    onClick={() => setModal({ kind: "section", id: null, data: { heading: "", body: "" } })}
                  >
                    ＋ section
                  </button>
                </div>
                {detail.sections.length === 0 && (
                  <span className="drawer-empty">No sections yet.</span>
                )}
                {detail.sections.map((sec) => (
                  <div className="panel" style={{ gap: 6 }} key={sec.id}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className="child-card-title" style={{ fontSize: 13.5 }}>
                        {sec.heading || "(untitled section)"}
                      </span>
                      <button
                        className="child-edit"
                        onClick={() =>
                          setModal({
                            kind: "section",
                            id: sec.id,
                            data: { heading: sec.heading, body: sec.body },
                          })
                        }
                      >
                        Edit
                      </button>
                      <button
                        className="child-delete"
                        disabled={deleteSection.isPending}
                        onClick={() =>
                          deleteSection.mutate(sec.id, {
                            onSuccess: () => showToast("Section deleted"),
                            onError: (err) => showToast(`Delete failed: ${err.message}`),
                          })
                        }
                      >
                        Delete
                      </button>
                    </div>
                    <span className="panel-note" style={{ whiteSpace: "pre-wrap" }}>{sec.body}</span>
                  </div>
                ))}
              </div>

              <div className="field" style={{ gap: 10 }}>
                <div className="board-toolbar">
                  <span className="field-label">RELATIONSHIPS &amp; BACKLINKS</span>
                  <div className="lens-toggle">
                    <button
                      className={`lens-option${relView === "list" ? " lens-option--active" : ""}`}
                      onClick={() => setRelView("list")}
                    >
                      List
                    </button>
                    <button
                      className={`lens-option${relView === "graph" ? " lens-option--active" : ""}`}
                      onClick={() => setRelView("graph")}
                    >
                      Graph
                    </button>
                  </div>
                  <button
                    className="board-new-scene"
                    onClick={() =>
                      setModal({
                        kind: "relationship",
                        data: { target: "", relationship_type: "mentions", direction: "directed" },
                      })
                    }
                  >
                    ＋ Link entity
                  </button>
                </div>

                {relView === "list" ? (
                  <div className="child-list" style={{ gap: 2 }}>
                    {detail.relationships.length === 0 && (
                      <span className="drawer-empty">No linked entities yet.</span>
                    )}
                    {detail.relationships.map((rel) => (
                      <div className="rel-row" key={rel.id}>
                        <span className="rel-glyph">
                          {rel.direction === "bidirectional" ? "↔" : rel.direction === "undirected" ? "—" : "→"}
                        </span>
                        <button
                          className="next-move-slug rel-target"
                          onClick={() => {
                            const target = relTargetLabel(rel, detail.id);
                            const match = entities.find(
                              (e) =>
                                e.id === target ||
                                e.slug === target ||
                                e.graph_endpoint_id.endsWith(target),
                            );
                            if (match) setSelection({ kind: "entity", id: match.id });
                          }}
                        >
                          {relTargetLabel(rel, detail.id)}
                        </button>
                        <span className="board-hint">{rel.relationship_type}</span>
                        <span className="chip" style={{ fontSize: 10, padding: "1px 7px" }}>
                          {rel.provenance}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rel-graph">
                    <div className="rel-graph-center">{detail.title}</div>
                    {detail.relationships.map((rel, i) => {
                      const n = detail.relationships.length;
                      const angle = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2;
                      const x = 50 + Math.cos(angle) * 36;
                      const y = 50 + Math.sin(angle) * 36;
                      const label = relTargetLabel(rel, detail.id);
                      return (
                        <div
                          className="rel-graph-node"
                          key={rel.id}
                          style={{ left: `${x}%`, top: `${y}%` }}
                          title={rel.relationship_type}
                        >
                          {label.length > 16 ? `${label.slice(0, 14)}…` : label}
                        </div>
                      );
                    })}
                    {detail.relationships.length === 0 && (
                      <span className="drawer-empty rel-graph-empty">No edges yet.</span>
                    )}
                  </div>
                )}
              </div>

              {detail.assets.length > 0 && (
                <div className="field" style={{ gap: 10 }}>
                  <span className="field-label">LINKED ASSETS</span>
                  <div className="pin-chip-row" style={{ gap: 12 }}>
                    {detail.assets.map((asset) => (
                      <div className="child-card child-card--row" style={{ padding: "10px 14px" }} key={asset.id}>
                        <AssetThumb asset={asset} className="entity-asset-thumb" />
                        <div className="pinned-meta">
                          <span className="pinned-name" style={{ fontSize: 12.5 }}>
                            {asset.title || asset.source_path}
                          </span>
                          <span
                            className="mono-inline"
                            style={{
                              fontSize: 10,
                              color: asset.mirror_state === "mirrored" ? "var(--teal)" : "var(--text-faint)",
                            }}
                          >
                            {asset.mirror_state.replace("_", " ")}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="child-list" style={{ maxWidth: 920, gap: 2 }}>
          <div className="source-grid source-grid--head">
            <span>PATH</span>
            <span>TITLE</span>
            <span>FRESHNESS</span>
          </div>
          {sources.map((src) => (
            <div className="source-grid source-grid--row" key={src.id}>
              <span className="mono-inline" style={{ color: "var(--text-body)", fontSize: 12 }}>
                {src.source_path}
              </span>
              <span className="panel-note">{src.title ?? ""}</span>
              <FreshnessBadge state={src.freshness_state} />
            </div>
          ))}
          {sources.length === 0 && <div className="empty-state">No lore sources ingested yet.</div>}
        </div>
      )}

      {modal && (
        <Modal
          title={
            modal.kind === "entity"
              ? modal.id != null
                ? "Edit entity"
                : "New entity"
              : modal.kind === "alias"
                ? "New alias"
                : modal.kind === "section"
                  ? modal.id != null
                    ? "Edit section"
                    : "New section"
                  : "Link entity"
          }
          onClose={() => setModal(null)}
          footer={
            <>
              <button className="btn-ghost" onClick={() => setModal(null)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={saveModal}>
                Save
              </button>
            </>
          }
        >
          {modal.kind === "entity" && (
            <>
              {modal.id == null && (
                <Field label="TYPE">
                  <PillSelect
                    options={ENTITY_TYPES}
                    value={(modal.data.entity_type as (typeof ENTITY_TYPES)[number]) ?? "article"}
                    onChange={(v) => setModal({ ...modal, data: { ...modal.data, entity_type: v } })}
                  />
                </Field>
              )}
              <Field label="TITLE">
                <input
                  className="input"
                  value={modal.data.title}
                  onChange={(e) => setModal({ ...modal, data: { ...modal.data, title: e.target.value } })}
                />
              </Field>
              <Field label="SUMMARY">
                <textarea
                  className="textarea"
                  value={modal.data.summary}
                  onChange={(e) => setModal({ ...modal, data: { ...modal.data, summary: e.target.value } })}
                />
              </Field>
            </>
          )}
          {modal.kind === "alias" && (
            <Field label="ALIAS">
              <input
                className="input"
                autoFocus
                value={modal.data.alias}
                onChange={(e) => setModal({ ...modal, data: { ...modal.data, alias: e.target.value } })}
              />
            </Field>
          )}
          {modal.kind === "section" && (
            <>
              <Field label="HEADING">
                <input
                  className="input"
                  autoFocus
                  value={modal.data.heading}
                  onChange={(e) => setModal({ ...modal, data: { ...modal.data, heading: e.target.value } })}
                />
              </Field>
              <Field label="BODY">
                <textarea
                  className="textarea textarea--tall"
                  value={modal.data.body}
                  onChange={(e) => setModal({ ...modal, data: { ...modal.data, body: e.target.value } })}
                />
              </Field>
              {modal.id == null && (
                <Field label="SOURCE" hint="which vault source this section belongs to">
                  <select
                    className="input"
                    value={modal.data.source_id ?? detail?.source_id ?? sources[0]?.id ?? ""}
                    onChange={(e) => setModal({ ...modal, data: { ...modal.data, source_id: e.target.value } })}
                  >
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title || s.source_path}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
            </>
          )}
          {modal.kind === "relationship" && (
            <>
              <Field label="TARGET ENTITY" hint="title or slug — unknown names are stored as unresolved targets">
                <input
                  className="input"
                  autoFocus
                  value={modal.data.target}
                  onChange={(e) => setModal({ ...modal, data: { ...modal.data, target: e.target.value } })}
                />
              </Field>
              <Field label="RELATIONSHIP TYPE">
                <input
                  className="input"
                  value={modal.data.relationship_type}
                  onChange={(e) =>
                    setModal({ ...modal, data: { ...modal.data, relationship_type: e.target.value } })
                  }
                />
              </Field>
              <Field label="DIRECTION">
                <PillSelect
                  options={["directed", "bidirectional", "undirected"] as const}
                  value={modal.data.direction as "directed"}
                  onChange={(v) => setModal({ ...modal, data: { ...modal.data, direction: v } })}
                />
              </Field>
            </>
          )}
        </Modal>
      )}

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
