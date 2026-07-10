import { useRef, useState } from "react";
import { Modal, Field } from "../components/Modal";
import { PillSelect } from "../components/PillSelect";
import {
  useClocksQuery,
  useClockDetailQuery,
  useClockTicksQuery,
  useCreateClock,
  useUpdateClock,
  useUpdateLifecycle,
  useTickClock,
  useAddClockLink,
  useCascadesQuery,
  useSaveCascade,
  useDeleteCascade,
  useFireCascade,
  useMirrorClock,
  useDriftCheck,
} from "../api/clocks";
import type { CascadeRule, Clock, ClockKind, FireResult } from "../types/clock";

type Env = "test" | "prod";

function clockGradient(clock: Clock): string {
  const angle = clock.segments > 0 ? (clock.filled / clock.segments) * 360 : 0;
  const fill = clock.kind === "countdown" ? "var(--amber-bright)" : "var(--teal)";
  return `conic-gradient(${fill} 0deg ${angle}deg, var(--surface-raised) ${angle}deg 360deg)`;
}

function mirrorBadge(clock: Clock, env: Env): { label: string; cls: string } {
  const mirror = clock.mirror;
  if (!mirror) return { label: "local only", cls: "" };
  const idForEnv = env === "test" ? mirror.foundry_clock_id_test : mirror.foundry_clock_id_prod;
  if (mirror.state === "failed" || mirror.state === "missing_mirror") {
    return { label: mirror.state.replace("_", " "), cls: "chip--red" };
  }
  if (mirror.state === "mirrored" && idForEnv) return { label: "mirrored", cls: "chip--teal" };
  return { label: "local only", cls: "" };
}

// ── Tick modal (reason is mandatory in the engine) ──────────────────────────

function TickModal({
  clock,
  delta,
  onClose,
  onResult,
}: {
  clock: Clock;
  delta: number;
  onClose: () => void;
  onResult: (result: FireResult) => void;
}) {
  const tick = useTickClock();
  const [reason, setReason] = useState("");

  return (
    <Modal
      title={`${delta > 0 ? "Tick" : "Untick"} — ${clock.name}`}
      titleAside={
        <span className="modal-title-aside">
          {clock.filled}/{clock.segments} → {Math.max(0, Math.min(clock.segments, clock.filled + delta))}/
          {clock.segments}
        </span>
      }
      onClose={onClose}
      footer={
        <>
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            disabled={!reason.trim() || tick.isPending}
            onClick={() =>
              tick.mutate(
                { id: clock.id, delta, reason: reason.trim() },
                { onSuccess: (result) => onResult(result) },
              )
            }
          >
            {tick.isPending ? "Ticking…" : "Apply tick"}
          </button>
        </>
      }
    >
      <Field label="REASON" hint="ticks are fiction events — the reason lands in the audit log and may fire cascades">
        <input
          className="input"
          type="text"
          autoFocus
          placeholder="What happened in the fiction?"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>
      {tick.isError && <span className="error-state">{tick.error.message}</span>}
    </Modal>
  );
}

// ── Cascade preview modal ────────────────────────────────────────────────────

function CascadePreview({
  title,
  result,
  clockName,
  onCommit,
  committing,
  onClose,
}: {
  title: string;
  result: FireResult;
  clockName: (id: string) => string;
  onCommit?: () => void;
  committing?: boolean;
  onClose: () => void;
}) {
  const depths = [...new Set([...result.applied, ...result.skipped].map((x) => x.hop_depth))].sort(
    (a, b) => a - b,
  );

  return (
    <Modal
      title={`Cascade ${result.dry_run ? "Preview" : "Result"} — ${title}`}
      titleAside={
        <span className="modal-title-aside">
          {result.dry_run ? "dry run · nothing committed" : "committed"}
        </span>
      }
      width={640}
      onClose={onClose}
      footer={
        <>
          {result.dry_run && onCommit && (
            <button className="btn btn-primary" disabled={committing} onClick={onCommit}>
              {committing ? "Committing…" : "Commit this fire"}
            </button>
          )}
          <button className="btn-ghost" onClick={onClose}>
            {result.dry_run ? "Cancel" : "Close"}
          </button>
          <span className="board-hint" style={{ marginLeft: "auto" }}>
            {result.applied.length} applied · {result.skipped.length} skipped ·{" "}
            {result.guard_trips.length} guard trips
          </span>
        </>
      }
    >
      {depths.length === 0 && <div className="empty-state">Nothing would move.</div>}
      {depths.map((depth) => (
        <div className="cascade-depth-row" key={depth}>
          <span className="cascade-depth-label">depth {depth}</span>
          <div className="cascade-depth-items">
            {result.applied
              .filter((t) => t.hop_depth === depth)
              .map((t, i) => (
                <div className="cascade-item cascade-item--applied" key={`a${i}`}>
                  <div className="cascade-item-top">
                    <span className="cascade-item-name">{clockName(t.clock_id)}</span>
                    <span className="cascade-item-delta">
                      {t.filled_before} → {t.filled_after}
                      {t.delta > 0 ? ` (+${t.delta})` : ` (${t.delta})`}
                    </span>
                    <span className="cascade-item-status cascade-item-status--applied">
                      {result.dry_run ? "WILL TICK" : "TICKED"}
                      {t.events.length > 0 ? ` · ${t.events.join(", ")}` : ""}
                    </span>
                  </div>
                  {t.reason && <span className="cascade-item-note">{t.reason}</span>}
                </div>
              ))}
            {result.skipped
              .filter((t) => t.hop_depth === depth)
              .map((t, i) => (
                <div className="cascade-item cascade-item--skipped" key={`s${i}`}>
                  <div className="cascade-item-top">
                    <span className="cascade-item-name">{clockName(t.clock_id)}</span>
                    <span className="cascade-item-delta">
                      {t.delta > 0 ? `+${t.delta}` : t.delta}
                    </span>
                    <span className="cascade-item-status cascade-item-status--skipped">SKIPPED</span>
                  </div>
                  <span className="cascade-item-note">{t.why}</span>
                </div>
              ))}
          </div>
        </div>
      ))}
      {result.guard_trips.length > 0 && (
        <div className="quick-draft-note">
          ⓘ {result.guard_trips.join(" · ")}
        </div>
      )}
      <div className="quick-draft-note">
        ⓘ Each rule fires once per cascade; chains stop at depth 5; overshooting deltas are
        clamped; effects on resolved/abandoned clocks are skipped, not applied.
      </div>
    </Modal>
  );
}

// ── Clock detail drawer ──────────────────────────────────────────────────────

function ClockDrawer({
  clock,
  env,
  rules,
  clockName,
  onClose,
  onTick,
  toast,
}: {
  clock: Clock;
  env: Env;
  rules: CascadeRule[];
  clockName: (id: string) => string;
  onClose: () => void;
  onTick: (clock: Clock, delta: number) => void;
  toast: (msg: string) => void;
}) {
  const { data: detail } = useClockDetailQuery(clock.id);
  const { data: ticks = [] } = useClockTicksQuery(clock.id);
  const lifecycle = useUpdateLifecycle();
  const mirror = useMirrorClock();
  const tick = useTickClock();
  const updateClock = useUpdateClock();

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(clock.name);
  const [editSegments, setEditSegments] = useState(clock.segments);

  const links = detail?.links ?? [];
  const threadLinks = links.filter((l) => l.target_id.startsWith("thread:"));
  const touchingRules = rules.filter(
    (r) =>
      r.trigger_clock_id === clock.id || r.effects.some((e) => e.clock_id === clock.id),
  );
  const badge = mirrorBadge(clock, env);
  const isActive = clock.lifecycle === "active";

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer" style={{ width: 380 }}>
        <div className="drawer-top">
          <div className="editor-drawer-heading">
            <span className="editor-drawer-title">{clock.name}</span>
            <span className={`mono-inline`} style={{ color: clock.kind === "countdown" ? "var(--amber-bright)" : "var(--teal)" }}>
              {clock.kind} · {clock.lifecycle}
            </span>
          </div>
          <button className="drawer-close" style={{ marginLeft: "auto" }} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="clock-drawer-ring-row">
          <div className="clock-big-ring" style={{ background: clockGradient(clock) }}>
            <div className="clock-big-ring-inner">
              {clock.filled}/{clock.segments}
            </div>
          </div>
          <div className="clock-drawer-tick-col">
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn-tick-up" disabled={!isActive} onClick={() => onTick(clock, 1)}>
                ＋ Tick
              </button>
              <button className="btn-tick-down" disabled={!isActive} onClick={() => onTick(clock, -1)}>
                − Untick
              </button>
            </div>
            <span className="board-hint">ticks fire cascade rules</span>
          </div>
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">
            SET / CORRECT <span className="field-label-aside">— applied as an audited tick</span>
          </span>
          <div className="pip-row">
            {Array.from({ length: clock.segments + 1 }, (_, n) => (
              <button
                key={n}
                className={`pip${n <= clock.filled ? " pip--filled" : ""}${n === clock.filled ? " pip--current" : ""}`}
                title={`set to ${n}`}
                disabled={tick.isPending || !isActive}
                onClick={() => {
                  const delta = n - clock.filled;
                  if (delta === 0) return;
                  tick.mutate(
                    { id: clock.id, delta, reason: `set/correct to ${n}/${clock.segments}` },
                    { onSuccess: () => toast(`Set ${clock.name} to ${n}/${clock.segments}`) },
                  );
                }}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">FOUNDRY MIRROR</span>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span className={`chip ${badge.cls}`}>{badge.label}</span>
            <button
              className="btn-ghost"
              style={{ padding: "4px 12px", fontSize: 12 }}
              disabled={mirror.isPending}
              onClick={() =>
                mirror.mutate(
                  {
                    id: clock.id,
                    env,
                    action: badge.label === "mirrored" ? "unmirror" : "establish",
                  },
                  {
                    onSuccess: () =>
                      toast("Mirror request staged — review it in Sync Center before it applies"),
                    onError: (err) => toast(`Mirror request failed: ${err.message}`),
                  },
                )
              }
            >
              {badge.label === "mirrored" ? "Unmirror…" : "Mirror to Foundry…"}
            </button>
          </div>
          <span className="field-hint">establish/unmirror is review-gated via Sync Center</span>
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">CONNECTIONS</span>
          {threadLinks.map((l) => (
            <div key={l.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span className="child-key">thread</span>
              <span className="next-move-slug">↳ {l.target_id.replace("thread:", "")}</span>
            </div>
          ))}
          {touchingRules.map((r) => (
            <div className="connection-row" key={r.id}>
              <span className="connection-name">{r.name || r.title}</span>
              <span
                className="mono-inline"
                style={{
                  fontSize: 10,
                  color: r.trigger_clock_id === clock.id ? "var(--amber-bright)" : "var(--azure-bright)",
                }}
              >
                {r.trigger_clock_id === clock.id ? "watches this" : "ticks this"}
              </span>
              <span
                className="mono-inline"
                style={{ marginLeft: "auto", fontSize: 10, color: r.enabled ? "var(--teal)" : "var(--text-faint)" }}
              >
                {r.enabled ? "enabled" : "disabled"}
              </span>
            </div>
          ))}
          {threadLinks.length === 0 && touchingRules.length === 0 && (
            <span className="drawer-empty">no thread link, no cascade rules touch this clock</span>
          )}
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">LIFECYCLE</span>
          <div style={{ display: "flex", gap: 8 }}>
            {isActive ? (
              <>
                <button
                  className="btn-tick-up"
                  onClick={() =>
                    lifecycle.mutate(
                      { id: clock.id, lifecycle: "resolved", resolution: "resolved from clock board" },
                      { onSuccess: () => toast(`${clock.name} resolved`) },
                    )
                  }
                >
                  ✓ Resolve
                </button>
                <button
                  className="btn-tick-down"
                  onClick={() =>
                    lifecycle.mutate(
                      { id: clock.id, lifecycle: "abandoned", resolution: "abandoned from clock board" },
                      { onSuccess: () => toast(`${clock.name} abandoned`) },
                    )
                  }
                >
                  Abandon
                </button>
              </>
            ) : (
              <button
                className="btn-ghost"
                onClick={() =>
                  lifecycle.mutate(
                    { id: clock.id, lifecycle: "active" },
                    { onSuccess: () => toast(`${clock.name} reactivated`) },
                  )
                }
              >
                ↻ Reactivate
              </button>
            )}
          </div>
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">MANAGE</span>
          {editing ? (
            <>
              <Field label="NAME">
                <input className="input" value={editName} onChange={(e) => setEditName(e.target.value)} />
              </Field>
              <Field label="SEGMENTS">
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={32}
                  value={editSegments}
                  onChange={(e) => setEditSegments(Number(e.target.value))}
                />
              </Field>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn btn-primary"
                  disabled={updateClock.isPending}
                  onClick={() =>
                    updateClock.mutate(
                      { id: clock.id, name: editName, segments: editSegments },
                      {
                        onSuccess: () => {
                          setEditing(false);
                          toast("Clock updated");
                        },
                      },
                    )
                  }
                >
                  Save
                </button>
                <button className="btn-ghost" onClick={() => setEditing(false)}>
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn-ghost" onClick={() => setEditing(true)}>
                ✎ Edit clock
              </button>
              {confirmingDelete ? (
                <button
                  className="btn-danger"
                  onClick={() =>
                    lifecycle.mutate(
                      { id: clock.id, lifecycle: "abandoned", resolution: "abandoned (delete request)" },
                      {
                        onSuccess: () => {
                          toast("Clock abandoned — history is append-only, so clocks are never hard-deleted");
                          onClose();
                        },
                      },
                    )
                  }
                >
                  Confirm abandon
                </button>
              ) : (
                <button className="btn-danger-ghost" onClick={() => setConfirmingDelete(true)}>
                  Abandon…
                </button>
              )}
            </div>
          )}
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">RECENT ACTIVITY</span>
          {ticks.length === 0 && <span className="drawer-empty">nothing yet</span>}
          {ticks.slice(0, 8).map((t) => (
            <span className="tick-history-line" key={t.id}>
              · {t.filled_before}→{t.filled_after} {t.rule_title ? `[${t.rule_title}] ` : ""}
              {t.reason}
            </span>
          ))}
        </div>
      </div>
    </>
  );
}

// ── Rule editor modal ────────────────────────────────────────────────────────

interface RuleDraft {
  id: string | null;
  name: string;
  trigger_clock_id: string;
  condValue: "half" | "full" | "any";
  effects: Array<{ clock_id: string; delta: number; reason_template: string }>;
}

function ruleToDraft(rule: CascadeRule | null, clocks: Clock[]): RuleDraft {
  const cond = (rule?.condition ?? {}) as { value?: unknown };
  const condValue = cond.value === "half" ? "half" : cond.value === "full" ? "full" : "any";
  return {
    id: rule?.id ?? null,
    name: rule?.name || rule?.title || "",
    trigger_clock_id: rule?.trigger_clock_id ?? clocks[0]?.id ?? "",
    condValue,
    effects: rule?.effects?.length
      ? rule.effects.map((e) => ({ ...e }))
      : [{ clock_id: clocks[0]?.id ?? "", delta: 1, reason_template: "" }],
  };
}

// ── Page ─────────────────────────────────────────────────────────────────────

export function ClockBoard() {
  const { data: clocks = [] } = useClocksQuery();
  const { data: rules = [] } = useCascadesQuery();
  const createClock = useCreateClock();
  const addLink = useAddClockLink();
  const saveCascade = useSaveCascade();
  const deleteCascade = useDeleteCascade();
  const fireCascade = useFireCascade();
  const driftCheck = useDriftCheck();

  const [tab, setTab] = useState<"board" | "cascades">("board");
  const [env, setEnv] = useState<Env>("test");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tickTarget, setTickTarget] = useState<{ clock: Clock; delta: number } | null>(null);
  const [fireResult, setFireResult] = useState<{ title: string; result: FireResult; ruleId?: string } | null>(null);
  const [newClock, setNewClock] = useState<{
    name: string;
    kind: ClockKind;
    segments: number;
    thread: string;
  } | null>(null);
  const [ruleModal, setRuleModal] = useState<RuleDraft | null>(null);
  const [confirmingRuleDelete, setConfirmingRuleDelete] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3600);
  }

  const clockName = (id: string) => clocks.find((c) => c.id === id)?.name ?? id.slice(0, 8);

  const active = clocks.filter((c) => c.lifecycle === "active");
  const inactive = clocks.filter((c) => c.lifecycle !== "active");
  const selected = clocks.find((c) => c.id === selectedId) ?? null;

  const mirroredCount = clocks.filter((c) => mirrorBadge(c, env).label === "mirrored").length;

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Clocks</h1>
          <span className="page-subtitle">
            {active.length} active · {inactive.length} resolved/abandoned · {mirroredCount} mirrored ·{" "}
            {rules.filter((r) => r.enabled).length} rules enabled
          </span>
        </div>
        <div className="header-actions">
          <button
            className={`chip${env === "prod" ? " chip--amber" : " chip--teal"}`}
            onClick={() => setEnv(env === "test" ? "prod" : "test")}
            title="Foundry environment for mirror/drift actions"
          >
            env: {env.toUpperCase()}
          </button>
          <button
            className="btn-ghost"
            disabled={driftCheck.isPending}
            onClick={() =>
              driftCheck.mutate(
                { env },
                {
                  onSuccess: (res) =>
                    showToast(
                      res.verdicts.length === 0
                        ? `Drift check (${res.env}): ${res.checked} mirrored clocks, no drift`
                        : `Drift check (${res.env}): ${res.verdicts.length} clock${res.verdicts.length > 1 ? "s" : ""} drifted — adopt via Sync Center`,
                    ),
                  onError: (err) => showToast(`Drift check failed: ${err.message}`),
                },
              )
            }
          >
            {driftCheck.isPending ? "Checking…" : "Check drift"}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => setNewClock({ name: "", kind: "countdown", segments: 6, thread: "" })}
          >
            ＋ New clock
          </button>
        </div>
      </header>

      <div className="tabs">
        <button className={`tab${tab === "board" ? " tab--active" : ""}`} onClick={() => setTab("board")}>
          Clock Board
        </button>
        <button
          className={`tab${tab === "cascades" ? " tab--active" : ""}`}
          onClick={() => setTab("cascades")}
        >
          Cascade Rules
        </button>
      </div>

      {tab === "board" && (
        <>
          <section className="board-main">
            <div className="board-toolbar">
              <h2 className="column-heading-label">ACTIVE</h2>
              <span className="lane-count">{active.length}</span>
              <span className="board-hint" style={{ marginLeft: "auto" }}>
                tick = fiction event, fires cascades · open a clock to set/correct
              </span>
            </div>
            {active.length === 0 && <div className="empty-state">No active clocks.</div>}
            <div className="clock-grid">
              {active.map((clock) => {
                const badge = mirrorBadge(clock, env);
                const full = clock.filled >= clock.segments;
                return (
                  <div
                    className={`clock-card${full ? " clock-card--full" : ""}`}
                    key={clock.id}
                    onClick={() => setSelectedId(clock.id)}
                  >
                    <div className="clock-card-top">
                      <div className="clock-mid-ring" style={{ background: clockGradient(clock) }}>
                        <div
                          className="clock-mid-ring-inner"
                          style={{
                            color: clock.kind === "countdown" ? "var(--amber-bright)" : "var(--teal-bright)",
                          }}
                        >
                          {clock.filled}/{clock.segments}
                        </div>
                      </div>
                      <div className="clock-card-main">
                        <span className="clock-card-name">{clock.name}</span>
                        <span
                          className="mono-inline"
                          style={{
                            fontSize: 10.5,
                            color: clock.kind === "countdown" ? "var(--amber-bright)" : "var(--teal)",
                          }}
                        >
                          {clock.kind}
                        </span>
                      </div>
                      <div className="clock-card-btns" onClick={(e) => e.stopPropagation()}>
                        <button
                          className="tick-btn tick-btn--up"
                          title="tick +1"
                          onClick={() => setTickTarget({ clock, delta: 1 })}
                        >
                          ＋
                        </button>
                        <button
                          className="tick-btn tick-btn--down"
                          title="tick −1"
                          onClick={() => setTickTarget({ clock, delta: -1 })}
                        >
                          −
                        </button>
                      </div>
                    </div>
                    <div className="clock-card-badges">
                      {full && <span className="chip chip--amber">FULL — resolve?</span>}
                      <span className={`chip ${badge.cls}`}>{badge.label}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="board-main">
            <div className="board-toolbar">
              <h2 className="column-heading-label">RESOLVED / ABANDONED</h2>
              <span className="lane-count">{inactive.length}</span>
            </div>
            {inactive.length === 0 && <div className="empty-state">Nothing resolved yet.</div>}
            <div className="clock-grid clock-grid--small">
              {inactive.map((clock) => (
                <div className="clock-card clock-card--inactive" key={clock.id} onClick={() => setSelectedId(clock.id)}>
                  <div className="clock-small-ring">
                    {clock.filled}/{clock.segments}
                  </div>
                  <div className="clock-card-main">
                    <span className="clock-card-name" style={{ color: "var(--text-muted)" }}>
                      {clock.name}
                    </span>
                    <span className="mono-inline" style={{ fontSize: 10, color: "var(--text-faint)" }}>
                      {clock.lifecycle}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {tab === "cascades" && (
        <div className="child-list">
          <div className="board-toolbar">
            <h2 className="column-heading-label">CASCADE RULES</h2>
            <span className="board-hint">automations that tick other clocks</span>
            <button
              className="btn btn-primary"
              style={{ marginLeft: "auto" }}
              onClick={() => setRuleModal(ruleToDraft(null, clocks))}
            >
              ＋ New rule
            </button>
          </div>

          {rules.length === 0 && <div className="empty-state">No cascade rules yet.</div>}

          {rules.map((rule) => {
            const cond = (rule.condition ?? {}) as { op?: string; value?: unknown };
            return (
              <div className={`child-card${rule.enabled ? "" : " rule-card--disabled"}`} key={rule.id}>
                <div className="child-card-top">
                  <span className="child-card-title">{rule.name || rule.title}</span>
                  <button
                    className={`chip${rule.enabled ? " chip--teal" : ""}`}
                    title="click to toggle"
                    onClick={() => saveCascade.mutate({ id: rule.id, enabled: !rule.enabled })}
                  >
                    {rule.enabled ? "ENABLED" : "DISABLED"}
                  </button>
                  <span className="board-hint" style={{ marginLeft: "auto" }}>
                    {rule.effects.length} effect{rule.effects.length === 1 ? "" : "s"}
                  </span>
                </div>

                <div className="field" style={{ gap: 8 }}>
                  <span className="field-label">TRIGGER</span>
                  <div className="rule-trigger-block">
                    <span style={{ color: "var(--azure-bright)" }}>{rule.trigger_kind}</span>:{" "}
                    <span style={{ color: "var(--text-high)" }}>
                      {rule.trigger_clock_id ? clockName(rule.trigger_clock_id) : "(manual)"}
                    </span>{" "}
                    <span style={{ color: "var(--azure-bright)" }}>{rule.trigger_event ?? ""}</span>
                    {cond.op && (
                      <div style={{ paddingLeft: 16, marginTop: 6 }}>
                        condition: <span style={{ color: "var(--azure-bright)" }}>op:{cond.op}</span>{" "}
                        <span style={{ color: "var(--teal-bright)" }}>"{String(cond.value)}"</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="field" style={{ gap: 8 }}>
                  <span className="field-label">EFFECTS</span>
                  {rule.effects.map((eff, i) => (
                    <div className="rule-effect-row" key={i}>
                      <span className="rule-effect-clock">{clockName(eff.clock_id)}</span>
                      <span className="board-hint">delta</span>
                      <span
                        className="mono-inline"
                        style={{ color: eff.delta > 0 ? "var(--amber-bright)" : "var(--teal-bright)" }}
                      >
                        {eff.delta > 0 ? `+${eff.delta}` : eff.delta}
                      </span>
                      {eff.reason_template && (
                        <span className="board-hint">— "{eff.reason_template}"</span>
                      )}
                    </div>
                  ))}
                </div>

                <div className="rule-actions">
                  <button
                    className="btn btn-primary"
                    disabled={fireCascade.isPending}
                    onClick={() =>
                      fireCascade.mutate(
                        { id: rule.id, dry_run: true, trigger_note: "manual fire from clock board" },
                        {
                          onSuccess: (result) =>
                            setFireResult({ title: rule.name || rule.title, result, ruleId: rule.id }),
                          onError: (err) => showToast(`Fire failed: ${err.message}`),
                        },
                      )
                    }
                  >
                    Fire (dry run)…
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => saveCascade.mutate({ id: rule.id, enabled: !rule.enabled })}
                  >
                    {rule.enabled ? "Disable" : "Enable"}
                  </button>
                  <button className="btn-ghost" onClick={() => setRuleModal(ruleToDraft(rule, clocks))}>
                    Edit rule
                  </button>
                  {confirmingRuleDelete === rule.id ? (
                    <button
                      className="btn-danger"
                      onClick={() =>
                        deleteCascade.mutate(rule.id, {
                          onSuccess: () => {
                            setConfirmingRuleDelete(null);
                            showToast("Rule deleted");
                          },
                        })
                      }
                    >
                      Confirm delete
                    </button>
                  ) : (
                    <button className="btn-danger-ghost" onClick={() => setConfirmingRuleDelete(rule.id)}>
                      Delete
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selected && (
        <ClockDrawer
          clock={selected}
          env={env}
          rules={rules}
          clockName={clockName}
          onClose={() => setSelectedId(null)}
          onTick={(clock, delta) => setTickTarget({ clock, delta })}
          toast={showToast}
        />
      )}

      {tickTarget && (
        <TickModal
          clock={tickTarget.clock}
          delta={tickTarget.delta}
          onClose={() => setTickTarget(null)}
          onResult={(result) => {
            setTickTarget(null);
            if (result.applied.length > 1 || result.skipped.length > 0 || result.guard_trips.length > 0) {
              setFireResult({ title: tickTarget.clock.name, result });
            } else {
              showToast(`${tickTarget.clock.name} ticked`);
            }
          }}
        />
      )}

      {fireResult && (
        <CascadePreview
          title={fireResult.title}
          result={fireResult.result}
          clockName={clockName}
          committing={fireCascade.isPending}
          onCommit={
            fireResult.ruleId
              ? () =>
                  fireCascade.mutate(
                    { id: fireResult.ruleId!, dry_run: false, trigger_note: "manual fire from clock board" },
                    {
                      onSuccess: (result) => setFireResult({ title: fireResult.title, result }),
                      onError: (err) => showToast(`Commit failed: ${err.message}`),
                    },
                  )
              : undefined
          }
          onClose={() => setFireResult(null)}
        />
      )}

      {newClock && (
        <Modal
          title="New clock"
          width={440}
          onClose={() => setNewClock(null)}
          footer={
            <>
              <button className="btn-ghost" onClick={() => setNewClock(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={!newClock.name.trim() || createClock.isPending}
                onClick={() =>
                  createClock.mutate(
                    { name: newClock.name.trim(), kind: newClock.kind, segments: newClock.segments },
                    {
                      onSuccess: (created) => {
                        if (newClock.thread.trim()) {
                          addLink.mutate({
                            id: created.id,
                            target_endpoint: `thread:${newClock.thread.trim()}`,
                            relationship_type: "tracks",
                          });
                        }
                        setNewClock(null);
                        showToast(
                          `${created.name} created — ${created.kind === "countdown" ? "countdowns start full" : "progress clocks start empty"}`,
                        );
                      },
                    },
                  )
                }
              >
                Create clock
              </button>
            </>
          }
        >
          <Field label="NAME">
            <input
              className="input"
              autoFocus
              placeholder="e.g. Winter Supplies Run Out"
              value={newClock.name}
              onChange={(e) => setNewClock({ ...newClock, name: e.target.value })}
            />
          </Field>
          <Field label="KIND">
            <PillSelect
              options={["countdown", "progress"] as const}
              value={newClock.kind}
              onChange={(kind) => setNewClock({ ...newClock, kind })}
              tone={newClock.kind === "countdown" ? "amber" : "teal"}
            />
          </Field>
          <Field label="SEGMENTS">
            <div className="pill-select">
              {[4, 6, 8, 10, 12].map((n) => (
                <button
                  key={n}
                  className={`pill-option${newClock.segments === n ? " pill-option--active pill-option--azure" : ""}`}
                  onClick={() => setNewClock({ ...newClock, segments: n })}
                >
                  {n}
                </button>
              ))}
            </div>
          </Field>
          <Field label="LINKED THREAD" hint="optional — thread slug, e.g. obsidian-court">
            <input
              className="input"
              style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}
              value={newClock.thread}
              onChange={(e) => setNewClock({ ...newClock, thread: e.target.value })}
            />
          </Field>
        </Modal>
      )}

      {ruleModal && (
        <Modal
          title={ruleModal.id ? "Edit cascade rule" : "New cascade rule"}
          width={560}
          onClose={() => setRuleModal(null)}
          footer={
            <>
              <button className="btn-ghost" onClick={() => setRuleModal(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={!ruleModal.name.trim() || saveCascade.isPending}
                onClick={() => {
                  const condition =
                    ruleModal.condValue === "any"
                      ? {}
                      : { clock: ruleModal.trigger_clock_id, op: "gte", value: ruleModal.condValue };
                  const payload = {
                    name: ruleModal.name.trim(),
                    title: ruleModal.name.trim(),
                    trigger_kind: "clock_event" as const,
                    trigger_clock_id: ruleModal.trigger_clock_id,
                    trigger_event: "ticked",
                    condition,
                    effects: ruleModal.effects.filter((e) => e.clock_id),
                    enabled: true,
                  };
                  saveCascade.mutate(ruleModal.id ? { id: ruleModal.id, ...payload } : payload, {
                    onSuccess: () => {
                      setRuleModal(null);
                      showToast("Rule saved");
                    },
                  });
                }}
              >
                {ruleModal.id ? "Save rule" : "Create rule"}
              </button>
            </>
          }
        >
          <Field label="NAME">
            <input
              className="input"
              autoFocus
              placeholder="e.g. Council Loses Patience"
              value={ruleModal.name}
              onChange={(e) => setRuleModal({ ...ruleModal, name: e.target.value })}
            />
          </Field>
          <Field label="TRIGGER — when this clock ticks…">
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <select
                className="input"
                style={{ flex: 1, minWidth: 180, width: "auto" }}
                value={ruleModal.trigger_clock_id}
                onChange={(e) => setRuleModal({ ...ruleModal, trigger_clock_id: e.target.value })}
              >
                {clocks.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <PillSelect
                options={["any", "half", "full"] as const}
                value={ruleModal.condValue}
                onChange={(condValue) => setRuleModal({ ...ruleModal, condValue })}
                labels={{ any: "any tick", half: "≥ half", full: "filled" }}
              />
            </div>
          </Field>
          <Field label="EFFECTS — …tick these clocks">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {ruleModal.effects.map((eff, i) => (
                <div className="rule-effect-editor" key={i}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <select
                      className="input"
                      style={{ flex: 1, width: "auto" }}
                      value={eff.clock_id}
                      onChange={(e) => {
                        const effects = [...ruleModal.effects];
                        effects[i] = { ...eff, clock_id: e.target.value };
                        setRuleModal({ ...ruleModal, effects });
                      }}
                    >
                      <option value="">— pick clock —</option>
                      {clocks.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    <button
                      className="tick-btn"
                      onClick={() => {
                        const effects = [...ruleModal.effects];
                        effects[i] = { ...eff, delta: eff.delta - 1 || -1 };
                        setRuleModal({ ...ruleModal, effects });
                      }}
                    >
                      −
                    </button>
                    <span
                      className="mono-inline"
                      style={{
                        width: 28,
                        textAlign: "center",
                        color: eff.delta > 0 ? "var(--amber-bright)" : "var(--teal-bright)",
                      }}
                    >
                      {eff.delta > 0 ? `+${eff.delta}` : eff.delta}
                    </span>
                    <button
                      className="tick-btn"
                      onClick={() => {
                        const effects = [...ruleModal.effects];
                        effects[i] = { ...eff, delta: eff.delta + 1 || 1 };
                        setRuleModal({ ...ruleModal, effects });
                      }}
                    >
                      ＋
                    </button>
                    <button
                      className="editor-clue-remove"
                      onClick={() =>
                        setRuleModal({ ...ruleModal, effects: ruleModal.effects.filter((_, j) => j !== i) })
                      }
                    >
                      ✕
                    </button>
                  </div>
                  <input
                    className="input"
                    placeholder="fiction note — why does this tick?"
                    value={eff.reason_template}
                    onChange={(e) => {
                      const effects = [...ruleModal.effects];
                      effects[i] = { ...eff, reason_template: e.target.value };
                      setRuleModal({ ...ruleModal, effects });
                    }}
                  />
                </div>
              ))}
              <button
                className="board-new-scene"
                style={{ marginLeft: 0, width: "fit-content" }}
                onClick={() =>
                  setRuleModal({
                    ...ruleModal,
                    effects: [...ruleModal.effects, { clock_id: "", delta: 1, reason_template: "" }],
                  })
                }
              >
                ＋ add effect
              </button>
            </div>
          </Field>
        </Modal>
      )}

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
