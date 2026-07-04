import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, GitBranch, ListFilter, RefreshCw } from "lucide-react";
import {
  useThreadDetailQuery,
  useThreadSummaryQuery,
  useThreadsQuery,
  useUpdateThread,
} from "../api/threads";
import type { Thread } from "../types/thread";

const STATE_LABELS = {
  current: "Current",
  needs_direction: "Needs Direction",
  stale: "Stale",
};

function stateClassName(state: string): string {
  return state === "current" ? "ok" : state === "stale" ? "bad" : "warn";
}

function priorityRank(priority: string): number {
  return { urgent: 0, high: 1, med: 2, low: 3 }[priority] ?? 4;
}

interface ThreadDirectionDraft {
  pressure: string;
  stakes: string;
  next_move: string;
  theme: string;
  clock_label: string;
  clock_value: string;
  clock_max: string;
  unresolved_questions: string;
}

function draftFromThread(thread: Thread): ThreadDirectionDraft {
  return {
    pressure: thread.pressure || "",
    stakes: thread.stakes || "",
    next_move: thread.next_move || "",
    theme: thread.theme || "",
    clock_label: thread.clock_label || "",
    clock_value: thread.clock_value == null ? "" : String(thread.clock_value),
    clock_max: thread.clock_max == null ? "" : String(thread.clock_max),
    unresolved_questions: thread.unresolved_questions.join("\n"),
  };
}

export default function ThreadDirectionDashboard({
  onStatusChange,
  onErrorChange,
}: {
  onStatusChange: (msg: string) => void;
  onErrorChange: (msg: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: summary } = useThreadSummaryQuery();
  const { data: threads = [], isLoading, error, refetch } = useThreadsQuery({
    status: statusFilter || undefined,
    q: query || undefined,
  });
  const sortedThreads = useMemo(
    () =>
      [...threads].sort(
        (a, b) =>
          priorityRank(a.priority) - priorityRank(b.priority) ||
          a.stale_state.state.localeCompare(b.stale_state.state) ||
          a.title.localeCompare(b.title)
      ),
    [threads]
  );
  const activeId = selectedId || sortedThreads[0]?.id || null;
  const { data: detail } = useThreadDetailQuery(activeId);
  const updateThread = useUpdateThread();
  const [draft, setDraft] = useState<ThreadDirectionDraft | null>(null);

  useEffect(() => {
    if (error) onErrorChange(error.message);
  }, [error, onErrorChange]);

  useEffect(() => {
    setDraft(detail ? draftFromThread(detail) : null);
  }, [detail?.id]);

  async function markTouched(thread: Thread) {
    try {
      await updateThread.mutateAsync({
        id: thread.id,
        freshness_state: "fresh",
        last_touched_at: new Date().toISOString(),
      });
      onStatusChange("Thread touched.");
    } catch (err) {
      onErrorChange(err instanceof Error ? err.message : String(err));
    }
  }

  async function importLegacyThreads() {
    try {
      const res = await fetch("/api/threads/import/review", { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      onStatusChange(
        `Thread import staged: ${result.created.length} new review(s), ${result.skipped.length} already pending.`
      );
    } catch (err) {
      onErrorChange(err instanceof Error ? err.message : String(err));
    }
  }

  async function saveDirection(thread: Thread) {
    if (!draft) return;
    try {
      await updateThread.mutateAsync({
        id: thread.id,
        pressure: draft.pressure,
        stakes: draft.stakes,
        next_move: draft.next_move,
        theme: draft.theme,
        clock_label: draft.clock_label || null,
        clock_value: draft.clock_value === "" ? null : Number(draft.clock_value),
        clock_max: draft.clock_max === "" ? null : Number(draft.clock_max),
        unresolved_questions: draft.unresolved_questions
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        freshness_state: "fresh",
        last_touched_at: new Date().toISOString(),
      });
      onStatusChange("Thread direction saved.");
    } catch (err) {
      onErrorChange(err instanceof Error ? err.message : String(err));
    }
  }

  function setDraftField<K extends keyof ThreadDirectionDraft>(field: K, value: ThreadDirectionDraft[K]) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
  }

  return (
    <div className="toolPanel thread-dashboard">
      <div className="panelHeader">
        <div>
          <h2>Thread Direction</h2>
        </div>
        <div className="panelHeaderActions">
          <button onClick={importLegacyThreads}>
            <GitBranch size={16} /> Import Legacy
          </button>
          <button onClick={() => refetch()}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      <div className="thread-summary-grid">
        <SummaryCard label="Active" value={summary?.active ?? 0} />
        <SummaryCard label="Stale" value={summary?.stale ?? 0} tone="bad" />
        <SummaryCard label="Needs Direction" value={summary?.needs_direction ?? 0} tone="warn" />
        <SummaryCard label="High Priority" value={summary?.high_priority ?? 0} />
      </div>

      {summary?.next_campaign_move && (
        <section className="thread-next-move">
          <span>Next Campaign Move</span>
          <strong>{summary.next_campaign_move.title}</strong>
          <p>{summary.next_campaign_move.next_move}</p>
        </section>
      )}

      <div className="thread-toolbar">
        <label className="field">
          <span>Search</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label className="field">
          <span>Status</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="introduced">Introduced</option>
            <option value="dormant">Dormant</option>
            <option value="resolved">Resolved</option>
          </select>
        </label>
      </div>

      <div className="thread-layout">
        <section className="thread-list" aria-label="Threads">
          <div className="thread-list-header">
            <ListFilter size={14} />
            <span>{isLoading ? "Loading" : `${sortedThreads.length} Threads`}</span>
          </div>
          {sortedThreads.map((thread) => (
            <button
              key={thread.id}
              className={`thread-row ${activeId === thread.id ? "active" : ""}`}
              onClick={() => setSelectedId(thread.id)}
            >
              <span className={`thread-state-dot ${stateClassName(thread.stale_state.state)}`} />
              <span className="thread-row-main">
                <strong>{thread.title}</strong>
                  <span>{thread.next_move || thread.pressure || thread.id}</span>
              </span>
              <span className={`thread-priority priority-${thread.priority}`}>{thread.priority}</span>
            </button>
          ))}
        </section>

        <section className="thread-detail">
          {detail ? (
            <>
              <div className="thread-detail-header">
                <div>
                  <div className="thread-kicker">
                    <GitBranch size={14} /> {detail.graph_endpoint_id}
                  </div>
                  <h3>{detail.title}</h3>
                </div>
                <button onClick={() => markTouched(detail)}>
                  <RefreshCw size={16} /> Touch
                </button>
              </div>

              <div className="thread-status-strip">
                <span className={`badge badge--${stateClassName(detail.stale_state.state)}`}>
                  {STATE_LABELS[detail.stale_state.state]}
                </span>
                <span className={`thread-priority priority-${detail.priority}`}>{detail.priority}</span>
                {detail.arc && <span className="thread-chip">{detail.arc}</span>}
              </div>

              <div className="thread-direction-grid">
                <InfoBlock label="Pressure" value={detail.pressure} />
                <InfoBlock label="Stakes" value={detail.stakes} />
                <InfoBlock label="Next Move" value={detail.next_move || ""} />
                <InfoBlock label="Theme" value={detail.theme} />
              </div>

              {detail.stale_state.reasons.length > 0 && (
                <div className="thread-warning">
                  <AlertTriangle size={16} />
                  <span>{detail.stale_state.reasons.join(", ")}</span>
                </div>
              )}

              {draft && (
                <form
                  className="thread-edit-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    saveDirection(detail);
                  }}
                >
                  <label className="field">
                    <span>Next move</span>
                    <textarea
                      value={draft.next_move}
                      onChange={(event) => setDraftField("next_move", event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span>Pressure</span>
                    <textarea
                      value={draft.pressure}
                      onChange={(event) => setDraftField("pressure", event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span>Stakes</span>
                    <textarea
                      value={draft.stakes}
                      onChange={(event) => setDraftField("stakes", event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span>Theme</span>
                    <input
                      value={draft.theme}
                      onChange={(event) => setDraftField("theme", event.target.value)}
                    />
                  </label>
                  <div className="thread-clock-row">
                    <label className="field">
                      <span>Clock</span>
                      <input
                        value={draft.clock_label}
                        onChange={(event) => setDraftField("clock_label", event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>Now</span>
                      <input
                        type="number"
                        min="0"
                        value={draft.clock_value}
                        onChange={(event) => setDraftField("clock_value", event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>Max</span>
                      <input
                        type="number"
                        min="0"
                        value={draft.clock_max}
                        onChange={(event) => setDraftField("clock_max", event.target.value)}
                      />
                    </label>
                  </div>
                  <label className="field">
                    <span>Unresolved questions</span>
                    <textarea
                      value={draft.unresolved_questions}
                      onChange={(event) => setDraftField("unresolved_questions", event.target.value)}
                    />
                  </label>
                  <button type="submit" disabled={updateThread.isPending}>
                    Save Direction
                  </button>
                </form>
              )}

              <LinkedSection title="Entities" rows={detail.linked.entities} getText={(row) => `${row.title} - ${row.entity_type}`} />
              <LinkedSection title="Sessions" rows={detail.linked.sessions} getText={(row) => `Session ${row.number} - ${row.name || row.status}`} />
              <LinkedSection title="Scenes" rows={detail.linked.scenes} getText={(row) => `${row.title} - ${row.purpose || row.status}`} />
              <LinkedSection title="Relationships" rows={detail.linked.relationships} getText={(row) => `${row.source_id} ${row.relationship_type} ${row.target_id || row.unresolved_target}`} />
            </>
          ) : (
            <div className="thread-empty">No thread selected.</div>
          )}
        </section>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, tone = "ok" }: { label: string; value: number; tone?: string }) {
  return (
    <div className={`thread-summary-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="thread-info-block">
      <span>{label}</span>
      <p>{value || "-"}</p>
    </div>
  );
}

function LinkedSection<T>({ title, rows, getText }: { title: string; rows: T[]; getText: (row: T) => string }) {
  return (
    <section className="thread-linked-section">
      <h4>{title}</h4>
      {rows.length === 0 ? (
        <p className="thread-muted">None</p>
      ) : (
        <div className="thread-linked-list">
          {rows.map((row, index) => (
            <div key={index} className="thread-linked-row">
              {getText(row)}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
