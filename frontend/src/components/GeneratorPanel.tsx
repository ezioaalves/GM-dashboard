import { useState } from "react";
import {
  useGeneratorTablesQuery,
  useRollGeneratorTable,
  usePatchGeneratorEntry,
} from "../api/generator";

interface HistoryEntry {
  table: string;
  text: string;
}

export function GeneratorPanel({ onClose }: { onClose: () => void }) {
  const { data: tables = [] } = useGeneratorTablesQuery();
  const roll = useRollGeneratorTable();
  const patchEntry = usePatchGeneratorEntry();

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [result, setResult] = useState<{ roll: string; text: string } | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");

  const selected = tables.find((t) => t.key === selectedKey) ?? tables[0] ?? null;

  return (
    <>
      <div className="drawer-overlay" style={{ zIndex: 40 }} onClick={onClose} />
      <div className="drawer generator-panel">
        <div className="editor-drawer-header">
          <div className="editor-drawer-heading">
            <span className="editor-drawer-title" style={{ fontSize: 15 }}>
              Generator
            </span>
            <span className="page-subtitle">
              random prep tables · rolls are not committed anywhere
            </span>
          </div>
          <button className="drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="editor-drawer-body" style={{ gap: 18, padding: "18px 22px" }}>
          <div className="field" style={{ gap: 6 }}>
            <span className="field-label">TABLE</span>
            {tables.map((table) => (
              <button
                key={table.key}
                className={`generator-table-row${selected?.key === table.key ? " generator-table-row--selected" : ""}`}
                onClick={() => {
                  setSelectedKey(table.key);
                  setResult(null);
                  setEditing(null);
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 500 }}>{table.label}</span>
                <span className="mono-inline" style={{ fontSize: 10.5, color: "var(--text-faint)" }}>
                  {table.die} · {table.entries.length} entries
                </span>
              </button>
            ))}
            {tables.length === 0 && <span className="drawer-empty">No tables seeded yet.</span>}
          </div>

          {selected && (
            <>
              <div className="field" style={{ gap: 10 }}>
                <button
                  className="btn-block"
                  disabled={roll.isPending}
                  onClick={() =>
                    roll.mutate(selected.key, {
                      onSuccess: (entry) => {
                        const text = entry.description
                          ? `${entry.name} — ${entry.description}`
                          : entry.name;
                        setResult({ roll: `${selected.die} → ${entry.roll}`, text });
                        setHistory((prev) => [{ table: selected.die, text }, ...prev].slice(0, 6));
                      },
                    })
                  }
                >
                  {roll.isPending ? "Rolling…" : `Roll ${selected.die}`}
                </button>
                {result && (
                  <div className="generator-result">
                    <span className="mono-inline" style={{ fontSize: 10, color: "var(--azure-bright)", fontWeight: 600 }}>
                      RESULT — {result.roll}
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 600, color: "var(--text-high)", lineHeight: 1.4 }}>
                      {result.text}
                    </span>
                  </div>
                )}
                <span className="field-hint">
                  ⚠ uniform random pick — the stored die weighting is not respected by the backend
                  yet
                </span>
              </div>

              <div className="field" style={{ gap: 6 }}>
                <span className="field-label">
                  ENTRIES <span className="field-label-aside">— click to edit</span>
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {selected.entries.map((entry) =>
                    editing === entry.roll ? (
                      <div className="generator-entry-edit" key={entry.roll}>
                        <span className="generator-entry-n">{entry.roll}</span>
                        <input
                          className="input"
                          style={{ flex: 1, width: "auto", padding: "6px 10px", fontSize: 12.5 }}
                          value={editDraft}
                          autoFocus
                          onChange={(e) => setEditDraft(e.target.value)}
                        />
                        <button
                          className="child-edit"
                          style={{ marginLeft: 0 }}
                          disabled={patchEntry.isPending}
                          onClick={() =>
                            patchEntry.mutate(
                              { key: selected.key, roll: entry.roll, name: editDraft },
                              { onSuccess: () => setEditing(null) },
                            )
                          }
                        >
                          Save
                        </button>
                      </div>
                    ) : (
                      <button
                        className="generator-entry"
                        key={entry.roll}
                        onClick={() => {
                          setEditing(entry.roll);
                          setEditDraft(entry.name);
                        }}
                      >
                        <span className="generator-entry-n">{entry.roll}</span>
                        <span style={{ fontSize: 12.5, color: "var(--text-body)", lineHeight: 1.4 }}>
                          {entry.name}
                          {entry.description ? ` — ${entry.description}` : ""}
                        </span>
                      </button>
                    ),
                  )}
                </div>
              </div>
            </>
          )}

          {history.length > 0 && (
            <div className="drawer-section" style={{ gap: 6 }}>
              <span className="drawer-section-label">THIS SESSION</span>
              {history.map((h, i) => (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 12, color: "var(--text-dim)" }}>
                  <span className="mono-inline" style={{ fontSize: 10.5, color: "var(--text-faint)", flex: "none" }}>
                    {h.table}
                  </span>
                  <span>{h.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
