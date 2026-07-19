import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Field } from "../components/Modal";
import { PillSelect } from "../components/PillSelect";
import type { PageKey } from "../components/Sidebar";
import { assetFileUrl, useAssetsQuery, usePatchAsset, type LoreAsset } from "../api/lore";
import { useWriteVaultMarkdown } from "../api/sessions";
import { api } from "../lib/api";

const UNAVAILABLE_MIRROR_STATES = new Set(["missing_source", "missing_mirror", "failed"]);

function AssetThumb({ asset, className }: { asset: LoreAsset; className: string }) {
  const [errored, setErrored] = useState(false);
  const canShowImage = !UNAVAILABLE_MIRROR_STATES.has(asset.mirror_state) && !errored;

  if (canShowImage) {
    return (
      <div className={className}>
        <img
          src={assetFileUrl(asset.id)}
          alt={asset.title || asset.source_path}
          loading="lazy"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => setErrored(true)}
        />
      </div>
    );
  }
  return (
    <div className={className}>
      <span className="mono-inline" style={{ fontSize: 10, color: "var(--text-faint)" }}>
        {asset.asset_type}
        {asset.width && asset.height ? ` · ${asset.width}×${asset.height}` : ""}
      </span>
    </div>
  );
}

const MIRROR_FILTERS = ["all", "mirrored", "not_mirrored", "stale_mirror", "failed"] as const;
const STATUS_FILTERS = ["all", "current", "variant", "rejected"] as const;

interface SearchHit {
  path: string;
  title: string;
  snippet: string;
  source_id?: string;
  source_commit?: string;
  heading?: string;
  audience?: string;
}

function MirrorBadge({ state }: { state: string }) {
  const cls =
    state === "mirrored"
      ? "chip--teal"
      : state === "failed" || state === "conflict"
        ? "chip--red"
        : state === "stale_mirror" || state === "missing_mirror"
          ? "chip--amber"
          : "";
  return <span className={`chip ${cls}`}>{(state || "not mirrored").replace(/_/g, " ").toUpperCase()}</span>;
}

function AssetDrawer({
  asset,
  onClose,
  toast,
}: {
  asset: LoreAsset;
  onClose: () => void;
  toast: (m: string) => void;
}) {
  const patchAsset = usePatchAsset();

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer drawer--wide" style={{ width: 520 }}>
        <div className="editor-drawer-header">
          <div className="editor-drawer-heading">
            <span className="editor-drawer-title" style={{ wordBreak: "break-all" }}>
              {asset.title || asset.source_path}
            </span>
            <span className="page-subtitle">{asset.source_path}</span>
          </div>
          <button className="drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="editor-drawer-body">
          <AssetThumb asset={asset} className="asset-thumb-lg" />

          <div className="adventure-summary-grid">
            <Field label="STATUS">
              <PillSelect
                options={["current", "variant", "rejected"] as const}
                value={asset.status as "current"}
                onChange={(status) =>
                  patchAsset.mutate(
                    { id: asset.id, status },
                    { onSuccess: () => toast(`Status → ${status}`) },
                  )
                }
              />
            </Field>
            <Field label="FRESHNESS">
              <span className="chip" style={{ width: "fit-content" }}>
                {(asset.freshness_state || "unknown").replace(/_/g, " ")}
              </span>
            </Field>
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">LINKED ENTITY</span>
            {asset.linked_entity_id ? (
              <span className="pin-chip" style={{ width: "fit-content" }}>
                entity:{asset.linked_entity_id.slice(0, 8)}…
              </span>
            ) : (
              <span className="drawer-empty">Not linked to any entity.</span>
            )}
          </div>

          <div className="foundry-panel">
            <span className="drawer-section-label">FOUNDRY MIRROR</span>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <MirrorBadge state={asset.mirror_state} />
              {asset.foundry_path && (
                <span className="mono-inline" style={{ fontSize: 10.5, color: "var(--text-faint)" }}>
                  {asset.foundry_path}
                </span>
              )}
            </div>
            <span className="field-hint">
              Mirror state is maintained by the asset scan/sync pipeline — establishing a mirror
              runs through the Sync Center review flow, not from here.
            </span>
          </div>
        </div>

        <div className="editor-drawer-footer">
          {asset.status !== "rejected" && (
            <button
              className="btn-danger-ghost"
              style={{ marginRight: "auto" }}
              disabled={patchAsset.isPending}
              onClick={() =>
                patchAsset.mutate(
                  { id: asset.id, status: "rejected" },
                  { onSuccess: () => toast("Asset marked rejected — the file on disk is untouched") },
                )
              }
            >
              Mark rejected
            </button>
          )}
          <button className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </>
  );
}

export function AssetsSearch({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const [tab, setTab] = useState<"assets" | "search">("assets");
  const [mirrorFilter, setMirrorFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [scanBanner, setScanBanner] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [includeArchive, setIncludeArchive] = useState(false);
  const [fileModal, setFileModal] = useState<{ path: string; body: string; dirty: boolean } | null>(
    null,
  );

  const { data: assets = [] } = useAssetsQuery();
  const writeVault = useWriteVaultMarkdown();
  const qc = useQueryClient();

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3600);
  }

  const filtered = assets.filter(
    (a) =>
      (mirrorFilter === "all" || a.mirror_state === mirrorFilter) &&
      (statusFilter === "all" || a.status === statusFilter),
  );

  const drawerAsset = assets.find((a) => a.id === drawerId) ?? null;

  async function scanAssets() {
    try {
      const summary = await api.post<Record<string, unknown>>("/api/assets/import/scan");
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["sync"] });
      setScanBanner(
        `Scan complete — new files are staged as pending reviews; changed/missing files get a direct fact-write. ${JSON.stringify(summary).slice(0, 120)}`,
      );
    } catch (err) {
      showToast(`Scan failed: ${(err as Error).message}`);
    }
  }

  async function runSearch() {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setLastQuery(q);
    try {
      setResults(await api.get<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&limit=20&include_archive=${includeArchive}`));
    } catch (err) {
      showToast(`Search failed: ${(err as Error).message}`);
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function openFile(path: string) {
    try {
      const data = await api.get<{ path: string; markdown: string }>(`/api/files/markdown?path=${encodeURIComponent(path)}`);
      setFileModal({ path: data.path, body: data.markdown, dirty: false });
    } catch (err) {
      showToast(`Open failed: ${(err as Error).message}`);
    }
  }

  function highlight(snippet: string, q: string) {
    const idx = snippet.toLowerCase().indexOf(q.toLowerCase());
    if (idx < 0) return <span className="search-snippet">…{snippet}…</span>;
    return (
      <span className="search-snippet">
        …{snippet.slice(0, idx)}
        <mark className="search-mark">{snippet.slice(idx, idx + q.length)}</mark>
        {snippet.slice(idx + q.length)}…
      </span>
    );
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Assets · Search</h1>
          <span className="page-subtitle">
            asset library with Foundry mirror state · raw vault search
          </span>
        </div>
        <div className="header-actions">
          <button className="btn-ghost" onClick={scanAssets}>
            ⟳ Scan asset folders
          </button>
        </div>
      </header>

      <div className="tabs">
        <button className={`tab${tab === "assets" ? " tab--active" : ""}`} onClick={() => setTab("assets")}>
          Assets
        </button>
        <button className={`tab${tab === "search" ? " tab--active" : ""}`} onClick={() => setTab("search")}>
          Vault Search
        </button>
      </div>

      {tab === "assets" && (
        <>
          {scanBanner && (
            <div className="quick-draft-note" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ flex: 1 }}>{scanBanner}</span>
              <button className="panel-link" style={{ background: "none", border: "none", flex: "none" }} onClick={() => onNavigate("sync-center")}>
                Review →
              </button>
              <button className="drawer-close" style={{ fontSize: 16 }} onClick={() => setScanBanner(null)}>
                ✕
              </button>
            </div>
          )}

          <div className="lens-filters" style={{ marginTop: 0 }}>
            <span className="field-label">MIRROR</span>
            {MIRROR_FILTERS.map((m) => (
              <button
                key={m}
                className={`lens-filter${mirrorFilter === m ? " lens-filter--active" : ""}`}
                onClick={() => setMirrorFilter(m)}
              >
                {m.replace("_", " ")}
              </button>
            ))}
            <span className="field-label" style={{ marginLeft: 14 }}>
              STATUS
            </span>
            {STATUS_FILTERS.map((m) => (
              <button
                key={m}
                className={`lens-filter${statusFilter === m ? " lens-filter--active" : ""}`}
                onClick={() => setStatusFilter(m)}
              >
                {m}
              </button>
            ))}
          </div>

          <div className="asset-grid">
            {filtered.map((asset) => (
              <button className="asset-card" key={asset.id} onClick={() => setDrawerId(asset.id)}>
                <AssetThumb asset={asset} className="asset-thumb" />
                <div className="asset-card-body">
                  <span className="asset-card-name">{asset.title || asset.source_path}</span>
                  <div className="deck-card-badges">
                    <span className="chip" style={{ fontSize: 10, padding: "2px 8px" }}>
                      {asset.status}
                    </span>
                    <MirrorBadge state={asset.mirror_state} />
                  </div>
                  <span className="mono-inline" style={{ fontSize: 10.5, color: "var(--text-faint)" }}>
                    {asset.width && asset.height ? `${asset.width}×${asset.height} · ` : ""}
                    {asset.source_path.split(".").pop()}
                  </span>
                </div>
              </button>
            ))}
          </div>
          {filtered.length === 0 && (
            <div className="empty-state">No assets match these filters.</div>
          )}
        </>
      )}

      {tab === "search" && (
        <div className="child-list" style={{ maxWidth: 820, gap: 16 }}>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              className="input"
              style={{ flex: 1, padding: "12px 16px", fontSize: 14 }}
              placeholder="Search canonical campaign Markdown…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
            />
            <button className="btn btn-primary" disabled={searching} onClick={runSearch}>
              {searching ? "Searching…" : "Search"}
            </button>
          </div>
          <span className="field-hint">
            Source-aware, unranked substring search. Campaign, mechanics, and agent sources are included by default;
            archive remains excluded unless explicitly enabled.
          </span>
          <label className="field-hint" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={includeArchive} onChange={(e) => setIncludeArchive(e.target.checked)} />
            Include historical archive (read-only)
          </label>

          {results && results.length > 0 && (
            <div className="child-list" style={{ gap: 8 }}>
              <span className="field-label">
                {results.length} FILES MATCHED "{lastQuery}"
              </span>
              {results.map((r) => (
                <button className="search-hit" key={`${r.source_id ?? "campaign-vault"}:${r.path}`} onClick={() => r.source_id === "campaign-vault" && openFile(r.path)}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="next-move-slug" style={{ fontSize: 11.5 }}>
                      {r.source_id ?? "campaign-vault"} · {r.path}{r.heading ? ` · ${r.heading}` : ""}
                    </span>
                    <span className="board-hint" style={{ marginLeft: "auto" }}>
                      {r.source_id === "campaign-vault" ? "open file →" : "provenance only"}
                    </span>
                  </div>
                  {highlight(r.snippet, lastQuery)}
                </button>
              ))}
            </div>
          )}
          {results && results.length === 0 && (
            <span className="drawer-empty">
              No substring match for "{lastQuery}" in the first pass. Try a shorter fragment.
            </span>
          )}
        </div>
      )}

      {drawerAsset && (
        <AssetDrawer asset={drawerAsset} onClose={() => setDrawerId(null)} toast={showToast} />
      )}

      {fileModal && (
        <div className="modal-overlay" onClick={() => setFileModal(null)}>
          <div className="modal file-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="editor-drawer-heading">
                <span className="modal-title mono-inline" style={{ color: "var(--text-high)", fontSize: 14 }}>
                  {fileModal.path}
                </span>
                <span className="page-subtitle">
                  raw vault markdown · save overwrites the file directly — no review gate
                </span>
              </div>
              <button className="modal-close" onClick={() => setFileModal(null)}>
                ✕
              </button>
            </div>
            <textarea
              className="file-modal-body"
              value={fileModal.body}
              onChange={(e) => setFileModal({ ...fileModal, body: e.target.value, dirty: true })}
            />
            <div className="modal-footer">
              {fileModal.dirty && (
                <span className="mono-inline" style={{ fontSize: 12, marginRight: "auto" }}>
                  unsaved changes
                </span>
              )}
              <button className="btn-ghost" onClick={() => setFileModal(null)}>
                Close
              </button>
              <button
                className="btn btn-primary"
                disabled={writeVault.isPending || !fileModal.dirty}
                onClick={() =>
                  writeVault.mutate(
                    { path: fileModal.path, content: fileModal.body },
                    {
                      onSuccess: () => {
                        setFileModal(null);
                        showToast("File written to vault — direct overwrite, no review");
                      },
                      onError: (err) => showToast(`Save failed: ${err.message}`),
                    },
                  )
                }
              >
                Save to vault
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
