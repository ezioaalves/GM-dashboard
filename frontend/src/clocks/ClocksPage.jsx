import React, { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  Clock as ClockIcon,
  History,
  Minus,
  Plus,
  RefreshCw,
  Share2,
  X,
} from "lucide-react";
import CustomSelect from "../components/CustomSelect";
import { ClockRing } from "./ClockRing";
import {
  useClockDetailQuery,
  useClocksQuery,
  useClockTicksQuery,
  useCreateClock,
  useDriftCheck,
  useMirrorClock,
  useTickClock,
  useUpdateLifecycle,
} from "../api/clocks";
import CascadePanel from "./CascadePanel";

// ── Static option lists ─────────────────────────────────────────────────────

const LIFECYCLE_FILTER_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "resolved", label: "Resolved" },
  { value: "abandoned", label: "Abandoned" },
  { value: "all", label: "All" },
];

const KIND_OPTIONS = [
  { value: "progress", label: "Progress (fills up)" },
  { value: "countdown", label: "Countdown (drains)" },
];

const VISIBILITY_OPTIONS = [
  { value: "gm", label: "GM only" },
  { value: "player", label: "Player-visible" },
  { value: "mixed", label: "Mixed" },
  { value: "unknown", label: "Unknown" },
];

const DEFAULT_NEW_CLOCK = {
  name: "",
  kind: "progress",
  segments: 6,
  description: "",
  segmentLabelsText: "",
  visibility: "gm",
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function mirrorChip(clock) {
  const { mirror, freshness_state } = clock;
  if (!mirror || mirror.state === "not_mirrored") return null;
  if (mirror.state === "failed" || mirror.state === "missing_mirror") {
    return { cls: "bad", label: mirror.state === "failed" ? "Mirror failed" : "Missing mirror" };
  }
  if (freshness_state === "stale_mirror") {
    return { cls: "warn", label: "Stale mirror" };
  }
  if (mirror.state === "mirrored") {
    return { cls: "ok", label: "Mirrored" };
  }
  return null;
}

function needsResolution(clock) {
  if (clock.lifecycle !== "active") return false;
  if (clock.kind === "countdown") return clock.filled === 0;
  return clock.filled === clock.segments;
}

function parseSegmentLabels(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .map((label, index) => ({ index, label }))
    .filter((entry) => entry.label.length > 0);
}

// ── Tick modal ───────────────────────────────────────────────────────────────

function TickModal({ clock, initialDelta, onClose, onConfirm, pending }) {
  const [delta, setDelta] = useState(initialDelta);
  const [reason, setReason] = useState("");

  const canConfirm = reason.trim().length > 0 && delta !== 0;

  return (
    <div className="modalBackdrop">
      <section className="markdownModal clock-modal">
        <header className="modalHeader">
          <div>
            <h2>Tick &ldquo;{clock.name}&rdquo;</h2>
            <p>
              Currently {clock.filled}/{clock.segments}. Applying this tick may trigger
              cascade rules on other clocks.
            </p>
          </div>
          <div className="modalActions">
            <button onClick={onClose}>
              <X size={16} /> Close
            </button>
          </div>
        </header>
        <div className="clock-modal-body">
          <label className="field">
            <span>Delta</span>
            <input
              type="number"
              value={delta}
              onChange={(e) => setDelta(parseInt(e.target.value, 10) || 0)}
            />
          </label>
          <label className="field">
            <span>Reason (required)</span>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is this clock moving?"
              autoFocus
            />
          </label>
          <div className="modalActions">
            <button
              className="active"
              disabled={!canConfirm || pending}
              onClick={() => onConfirm(delta, reason.trim())}
            >
              {pending ? "Applying…" : "Confirm"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

// ── Resolve modal ────────────────────────────────────────────────────────────

function ResolveModal({ clock, onClose, onConfirm, pending }) {
  const [resolution, setResolution] = useState("");

  return (
    <div className="modalBackdrop">
      <section className="markdownModal clock-modal">
        <header className="modalHeader">
          <div>
            <h2>Resolve &ldquo;{clock.name}&rdquo;</h2>
            <p>This clock is full but still active. Record how it resolved.</p>
          </div>
          <div className="modalActions">
            <button onClick={onClose}>
              <X size={16} /> Close
            </button>
          </div>
        </header>
        <div className="clock-modal-body">
          <label className="field">
            <span>Resolution</span>
            <textarea
              value={resolution}
              onChange={(e) => setResolution(e.target.value)}
              rows={3}
              placeholder="What happened when this clock filled/drained?"
              autoFocus
            />
          </label>
          <div className="modalActions">
            <button onClick={() => onConfirm("abandoned", resolution.trim())} disabled={pending}>
              Abandon
            </button>
            <button
              className="active"
              disabled={pending || !resolution.trim()}
              onClick={() => onConfirm("resolved", resolution.trim())}
            >
              {pending ? "Saving…" : "Resolve"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

// ── Clock card ───────────────────────────────────────────────────────────────

function ClockCard({ clock, onTick, onResolve, onMirror }) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const { data: ticks = [], isLoading: ticksLoading } = useClockTicksQuery(
    historyOpen ? clock.id : null
  );
  const { data: detail } = useClockDetailQuery(historyOpen ? clock.id : null);

  const chip = mirrorChip(clock);
  const flagged = needsResolution(clock);
  const remainingLabel =
    clock.kind === "countdown"
      ? `${clock.filled} left of ${clock.segments}`
      : `${clock.filled}/${clock.segments}`;

  // Group ticks visually by trigger_fire_id: ticks sharing a fire id get a
  // shared background band.
  let lastFireId = null;

  return (
    <article className={`clock-card${flagged ? " clock-card--flagged" : ""}`}>
      <div className="clock-card-top">
        <ClockRing segments={clock.segments} filled={clock.filled} kind={clock.kind} size={64} />
        <div className="clock-card-info">
          <h3>{clock.name}</h3>
          <p className="clock-card-count">{remainingLabel}</p>
          <div className="clock-card-badges">
            <span className={`badge badge--${clock.lifecycle === "active" ? "ok" : "warn"}`}>
              {clock.lifecycle}
            </span>
            {chip && <span className={`badge badge--${chip.cls}`}>{chip.label}</span>}
          </div>
        </div>
      </div>

      {clock.description && <p className="clock-card-desc">{clock.description}</p>}

      {flagged && (
        <div className="clock-card-flag">
          <AlertTriangle size={14} />
          <span>Needs resolution</span>
          <button onClick={() => onResolve(clock)}>Resolve</button>
        </div>
      )}

      {historyOpen && detail?.links?.length > 0 && (
        <div className="clock-link-chips">
          {detail.links.map((link) => (
            <span key={link.id} className="badge">
              {link.target_type}: {link.target_id.split(":").slice(1).join(":") || link.target_id}
            </span>
          ))}
        </div>
      )}

      <div className="clock-card-actions">
        <button
          aria-label="Decrease"
          onClick={() => onTick(clock, -1)}
          disabled={clock.lifecycle !== "active"}
        >
          <Minus size={14} />
        </button>
        <button
          aria-label="Increase"
          onClick={() => onTick(clock, 1)}
          disabled={clock.lifecycle !== "active"}
        >
          <Plus size={14} />
        </button>
        <button onClick={() => setHistoryOpen((v) => !v)}>
          <History size={14} /> History
          <ChevronDown size={12} className={historyOpen ? "clock-chevron open" : "clock-chevron"} />
        </button>
        <button onClick={() => onMirror(clock)}>
          <Share2 size={14} /> Mirror to Foundry (test)
        </button>
      </div>

      {historyOpen && (
        <div className="clock-history">
          {ticksLoading && <p className="clock-history-empty">Loading ticks…</p>}
          {!ticksLoading && ticks.length === 0 && (
            <p className="clock-history-empty">No ticks recorded yet.</p>
          )}
          {ticks.map((tick) => {
            const newGroup = tick.trigger_fire_id !== lastFireId;
            lastFireId = tick.trigger_fire_id;
            return (
              <div
                key={tick.id}
                className={`clock-history-row${newGroup ? " clock-history-row--group-start" : ""}`}
              >
                <span className={`clock-history-delta ${tick.delta >= 0 ? "up" : "down"}`}>
                  {tick.delta >= 0 ? `+${tick.delta}` : tick.delta}
                </span>
                <span className="clock-history-reason">{tick.reason}</span>
                <span className="clock-history-meta">
                  {tick.caused_by}
                  {tick.hop_depth > 0 && (
                    <span className="badge badge--warn clock-hop-badge">hop {tick.hop_depth}</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </article>
  );
}

// ── Clocks page ──────────────────────────────────────────────────────────────

export default function ClocksPage() {
  const queryClient = useQueryClient();
  const [lifecycleFilter, setLifecycleFilter] = useState("active");
  const [formOpen, setFormOpen] = useState(false);
  const [newClock, setNewClock] = useState(DEFAULT_NEW_CLOCK);
  const [tickTarget, setTickTarget] = useState(null); // { clock, initialDelta }
  const [resolveTarget, setResolveTarget] = useState(null); // clock
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [driftResult, setDriftResult] = useState(null);

  const queryParams = useMemo(
    () => (lifecycleFilter === "all" ? {} : { lifecycle: lifecycleFilter }),
    [lifecycleFilter]
  );
  const { data: clocks = [], isLoading, error: clocksError } = useClocksQuery(queryParams);

  const createMutation = useCreateClock();
  const tickMutation = useTickClock();
  const lifecycleMutation = useUpdateLifecycle();
  const mirrorMutation = useMirrorClock();
  const driftMutation = useDriftCheck();

  const clockNameById = useMemo(() => {
    const map = new Map();
    for (const c of clocks) map.set(c.id, c.name);
    return map;
  }, [clocks]);

  function resetError() {
    setError("");
  }

  async function handleCreate() {
    resetError();
    try {
      await createMutation.mutateAsync({
        name: newClock.name.trim(),
        kind: newClock.kind,
        segments: Number(newClock.segments) || 1,
        description: newClock.description.trim(),
        segment_labels: parseSegmentLabels(newClock.segmentLabelsText),
        visibility: newClock.visibility,
      });
      setStatus(`Clock "${newClock.name.trim()}" created.`);
      setNewClock(DEFAULT_NEW_CLOCK);
      setFormOpen(false);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function handleTickConfirm(delta, reason) {
    if (!tickTarget) return;
    resetError();
    try {
      const result = await tickMutation.mutateAsync({ id: tickTarget.clock.id, delta, reason });
      setTickTarget(null);
      if (result.applied && result.applied.length > 1) {
        const names = result.applied
          .map((a) => clockNameById.get(a.clock_id) || a.clock_id)
          .join(", ");
        setStatus(`Cascade: ${result.applied.length} clocks moved — ${names}`);
      } else {
        setStatus(`Tick applied to "${tickTarget.clock.name}".`);
      }
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function handleResolveConfirm(lifecycle, resolution) {
    if (!resolveTarget) return;
    resetError();
    try {
      await lifecycleMutation.mutateAsync({ id: resolveTarget.id, lifecycle, resolution });
      setStatus(`"${resolveTarget.name}" marked ${lifecycle}.`);
      setResolveTarget(null);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function handleMirror(clock) {
    resetError();
    try {
      await mirrorMutation.mutateAsync({ id: clock.id, env: "test", action: "establish" });
      setStatus(`Review created for "${clock.name}" — approve in sync reviews.`);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function handleDriftCheck() {
    resetError();
    setDriftResult(null);
    try {
      const result = await driftMutation.mutateAsync({ env: "test" });
      setDriftResult(result);
      setStatus(`Drift check: ${result.verdicts.length} of ${result.checked} clocks drifted.`);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function handleRepush(clockId) {
    resetError();
    try {
      await mirrorMutation.mutateAsync({ id: clockId, env: "test", action: "establish" });
      setStatus(`Re-pushed current state for ${clockNameById.get(clockId) || clockId}.`);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function handleAdopt(clockId) {
    const reason = window.prompt("Reason for adopting the Foundry-side value?");
    if (!reason) return;
    resetError();
    try {
      const res = await fetch(`/api/clocks/${clockId}/mirror/adopt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ env: "test", reason }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus(`Adopted Foundry state for ${clockNameById.get(clockId) || clockId}.`);
      setDriftResult((prev) =>
        prev ? { ...prev, verdicts: prev.verdicts.filter((v) => v.clock_id !== clockId) } : prev
      );
      queryClient.invalidateQueries({ queryKey: ["clocks"] });
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  const displayError = error || (clocksError ? clocksError.message : "");

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>Clocks</h2>
          <p>Progress and countdown clocks tracking campaign pressure.</p>
        </div>
        <div className="clock-header-actions">
          <CustomSelect
            value={lifecycleFilter}
            onChange={setLifecycleFilter}
            options={LIFECYCLE_FILTER_OPTIONS}
          />
          <button onClick={() => setFormOpen((v) => !v)}>
            <Plus size={16} /> New Clock
          </button>
        </div>
      </div>

      {(status || displayError) && (
        <section className={`notice ${displayError ? "bad" : "ok"}`}>
          <span>{displayError || status}</span>
          <button
            aria-label="Dismiss"
            onClick={() => {
              setStatus("");
              setError("");
            }}
          >
            <X size={14} />
          </button>
        </section>
      )}

      <div className="clock-drift-bar">
        <button onClick={handleDriftCheck} disabled={driftMutation.isPending}>
          <RefreshCw size={14} /> Check Foundry drift (test)
        </button>
        {driftResult && driftResult.verdicts.length === 0 && (
          <span className="clock-drift-clean">No drift detected across {driftResult.checked} clocks.</span>
        )}
      </div>

      {driftResult && driftResult.verdicts.length > 0 && (
        <div className="clock-drift-results">
          {driftResult.verdicts.map((v) => (
            <div key={v.clock_id} className="notice warn clock-drift-verdict">
              <span>
                <strong>{clockNameById.get(v.clock_id) || v.clock_id}</strong> —{" "}
                {v.kind === "missing_mirror" ? "missing on Foundry" : "value drift"}
                {v.fields && (
                  <code className="clock-drift-fields">
                    {Object.entries(v.fields)
                      .map(([f, vals]) => `${f}: engine=${vals.engine} foundry=${vals.foundry}`)
                      .join("; ")}
                  </code>
                )}
              </span>
              <div className="modalActions">
                <button onClick={() => handleRepush(v.clock_id)}>Re-push</button>
                <button onClick={() => handleAdopt(v.clock_id)}>Adopt</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {formOpen && (
        <div className="clock-create-form">
          <div className="formGrid">
            <label className="field spanAll">
              <span>Name</span>
              <input
                value={newClock.name}
                onChange={(e) => setNewClock((p) => ({ ...p, name: e.target.value }))}
                placeholder="Village Suspicion, Escape the Compound…"
              />
            </label>
            <label className="field">
              <span>Kind</span>
              <CustomSelect
                value={newClock.kind}
                onChange={(v) => setNewClock((p) => ({ ...p, kind: v }))}
                options={KIND_OPTIONS}
              />
              {newClock.kind === "countdown" && (
                <span className="clock-form-hint">Starts full and drains.</span>
              )}
            </label>
            <label className="field">
              <span>Segments</span>
              <input
                type="number"
                min={1}
                max={12}
                value={newClock.segments}
                onChange={(e) => setNewClock((p) => ({ ...p, segments: e.target.value }))}
              />
            </label>
            <label className="field">
              <span>Visibility</span>
              <CustomSelect
                value={newClock.visibility}
                onChange={(v) => setNewClock((p) => ({ ...p, visibility: v }))}
                options={VISIBILITY_OPTIONS}
              />
            </label>
            <label className="field spanAll">
              <span>Description</span>
              <textarea
                value={newClock.description}
                onChange={(e) => setNewClock((p) => ({ ...p, description: e.target.value }))}
                rows={2}
              />
            </label>
            <label className="field spanAll">
              <span>Segment labels (one per line, top to bottom)</span>
              <textarea
                value={newClock.segmentLabelsText}
                onChange={(e) => setNewClock((p) => ({ ...p, segmentLabelsText: e.target.value }))}
                rows={2}
                placeholder="Optional — e.g. Rumors spread / Patrols increase / Gates close"
              />
            </label>
          </div>
          <div className="saveActions">
            <button onClick={() => setFormOpen(false)}>Cancel</button>
            <button
              className="active"
              disabled={!newClock.name.trim() || createMutation.isPending}
              onClick={handleCreate}
            >
              {createMutation.isPending ? "Creating…" : "Create Clock"}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>Loading clocks…</p>
      ) : clocks.length === 0 ? (
        <p className="clock-empty">
          <ClockIcon size={14} /> No clocks match this filter yet.
        </p>
      ) : (
        <div className="clock-grid">
          {clocks.map((clock) => (
            <ClockCard
              key={clock.id}
              clock={clock}
              onTick={(c, delta) => setTickTarget({ clock: c, initialDelta: delta })}
              onResolve={(c) => setResolveTarget(c)}
              onMirror={handleMirror}
            />
          ))}
        </div>
      )}

      <CascadePanel
        clocks={clocks}
        clockNameById={clockNameById}
        onStatus={setStatus}
        onError={setError}
      />

      {tickTarget && (
        <TickModal
          clock={tickTarget.clock}
          initialDelta={tickTarget.initialDelta}
          pending={tickMutation.isPending}
          onClose={() => setTickTarget(null)}
          onConfirm={handleTickConfirm}
        />
      )}

      {resolveTarget && (
        <ResolveModal
          clock={resolveTarget}
          pending={lifecycleMutation.isPending}
          onClose={() => setResolveTarget(null)}
          onConfirm={handleResolveConfirm}
        />
      )}
    </div>
  );
}
