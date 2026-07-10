import { useMemo, useRef, useState } from "react";
import { SceneTypeBadge, TierBadge, sceneClueRows } from "../components/SceneBits";
import { useSessionsQuery, usePatchSessionFields } from "../api/sessions";
import { useScenesQuery } from "../api/scenes";
import { useClocksQuery, useTickClock } from "../api/clocks";
import { useFoundryStatusQuery } from "../api/cockpit";
import { useGeneratorTablesQuery, useRollGeneratorTable } from "../api/generator";
import type { Session, WrapCapture } from "../types/session";
import type { Scene } from "../types/scene";

function pickRunSession(sessions: Session[]): Session | null {
  return (
    sessions.find((s) => s.status === "ready") ??
    sessions.find((s) => s.status === "planned") ??
    null
  );
}

export function RunMode({ onExit }: { onExit: () => void }) {
  const { data: sessions = [] } = useSessionsQuery();
  const { data: scenes = [] } = useScenesQuery();
  const { data: clocks = [] } = useClocksQuery({ lifecycle: "active" });
  const { data: foundryStatus } = useFoundryStatusQuery();
  const { data: tables = [] } = useGeneratorTablesQuery();

  const tick = useTickClock();
  const roll = useRollGeneratorTable();
  const patchSession = usePatchSessionFields();

  const session = pickRunSession(sessions);

  const ordered = useMemo(
    () =>
      scenes
        .filter((s) => s.session_id === session?.id && s.placement === "ordered")
        .sort((a, b) => a.sort_order - b.sort_order),
    [scenes, session],
  );
  const floating = useMemo(
    () =>
      scenes
        .filter((s) => s.session_id === session?.id && s.placement === "floating")
        .sort((a, b) => a.sort_order - b.sort_order),
    [scenes, session],
  );

  const [currentId, setCurrentId] = useState<number | null>(null);
  const [playedIds, setPlayedIds] = useState<Set<number>>(new Set());
  const [note, setNote] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4200);
  }

  const current: Scene | null =
    scenes.find((s) => s.id === currentId) ??
    ordered.find((s) => !playedIds.has(s.id)) ??
    ordered[0] ??
    null;

  const orderedIndex = current ? ordered.findIndex((s) => s.id === current.id) : -1;
  const clues = current ? sceneClueRows(current) : [];
  const hasBranching =
    !!current && !!(current.if_succeed || current.if_fail || current.if_ignore || current.if_short);
  const connected = foundryStatus?.state === "configured";

  function saveNote() {
    if (!session || !note.trim()) return;
    const wrap = (session.wrap_capture ?? {}) as WrapCapture & { run_notes?: string };
    const prev = wrap.run_notes ?? "";
    const line = current ? `[${current.title}] ${note.trim()}` : note.trim();
    patchSession.mutate(
      {
        id: session.id,
        wrap_capture: { ...wrap, run_notes: prev ? `${prev}\n${line}` : line } as Record<string, unknown>,
      },
      {
        onSuccess: () => {
          setNote("");
          showToast("Note saved — feeds into wrap capture");
        },
      },
    );
  }

  function advance() {
    if (!current) return;
    setPlayedIds(new Set([...playedIds, current.id]));
    const next = ordered.find((s) => s.id !== current.id && !playedIds.has(s.id) && s.sort_order >= current.sort_order);
    setCurrentId(next?.id ?? null);
  }

  function tickClock(clockId: string, delta: number) {
    const clock = clocks.find((c) => c.id === clockId);
    if (!clock) return;
    tick.mutate(
      {
        id: clockId,
        delta,
        reason: current
          ? `Run mode — during "${current.title}"`
          : `Run mode — session ${session?.number ?? "?"}`,
      },
      {
        onSuccess: (result) => {
          const cascaded = result.applied.filter((a) => a.hop_depth > 0);
          showToast(
            cascaded.length > 0
              ? `${clock.name} ticked — cascade also moved ${cascaded.length} other clock${cascaded.length > 1 ? "s" : ""}`
              : `${clock.name}: ${result.clocks[clockId]?.filled}/${clock.segments}`,
          );
        },
        onError: (err) => showToast(`Tick failed: ${err.message}`),
      },
    );
  }

  const rollTables = tables.slice(0, 2);

  if (!session) {
    return (
      <div className="run-shell">
        <header className="run-topbar">
          <span className="run-badge">RUN MODE</span>
          <span className="run-session-name">No session is planned or ready</span>
          <div className="run-topbar-right">
            <button className="btn-ghost" onClick={onExit}>
              Exit Run mode
            </button>
          </div>
        </header>
        <div className="empty-state" style={{ margin: 40 }}>
          Plan a session first, then enter Run mode from the sidebar.
        </div>
      </div>
    );
  }

  return (
    <div className="run-shell">
      <header className="run-topbar">
        <span className="run-badge">RUN MODE</span>
        <span className="run-session-name">
          Session {session.number} — {session.name || "TBD"}
        </span>
        <span className="page-subtitle">
          {orderedIndex >= 0 ? `scene ${orderedIndex + 1} of ${ordered.length}` : `${ordered.length} scenes`} ·
          ordered spine
        </span>
        <div className="run-topbar-right">
          <div className="sidebar-foundry" style={{ padding: 0 }}>
            <span className={`sidebar-foundry-dot sidebar-foundry-dot--${connected ? "on" : "off"}`} />
            Foundry {connected ? "configured" : "offline"}
          </div>
          <button className="btn-ghost" onClick={onExit}>
            Exit Run mode
          </button>
        </div>
      </header>

      <div className="run-body">
        {/* left: scene spine */}
        <aside className="run-spine">
          <span className="drawer-section-label" style={{ padding: "0 6px 4px" }}>
            SCENE SPINE
          </span>
          {ordered.map((scene) => {
            const played = playedIds.has(scene.id);
            const isCurrent = current?.id === scene.id;
            return (
              <button
                key={scene.id}
                className={`spine-card${isCurrent ? " spine-card--current" : ""}${played ? " spine-card--played" : ""}`}
                onClick={() => setCurrentId(scene.id)}
              >
                <div className="spine-card-top">
                  {played ? (
                    <span className="spine-check">✓</span>
                  ) : (
                    <SceneTypeBadge type={scene.scene_type} />
                  )}
                  <span className="spine-card-title">{scene.title}</span>
                </div>
                {isCurrent && <span className="spine-now">● now playing</span>}
              </button>
            );
          })}
          {ordered.length === 0 && <span className="drawer-empty">No ordered scenes.</span>}

          <div className="run-floating">
            <span className="drawer-section-label" style={{ padding: "0 6px" }}>
              FLOATING
            </span>
            {floating.map((scene) => (
              <button key={scene.id} className="floating-card" onClick={() => setCurrentId(scene.id)}>
                {scene.title}
              </button>
            ))}
            {floating.length === 0 && <span className="drawer-empty">Nothing floating.</span>}
          </div>
        </aside>

        {/* center: current scene */}
        <section className="run-center">
          {current ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className={`type-chip type-chip--${current.scene_type}`}>
                  {current.scene_type} scene
                </span>
                <h1 className="run-scene-title">{current.title}</h1>
              </div>
              {current.description && <p className="run-scene-desc">{current.description}</p>}

              {hasBranching && (
                <div className="panel" style={{ gap: 9 }}>
                  <span className="field-label">IF THE TABLE...</span>
                  <div className="branching-list" style={{ fontSize: 12 }}>
                    {current.if_succeed && (
                      <div className="branching-row">
                        <span className="branching-key branching-key--succeed">succeed</span>
                        <span>{current.if_succeed}</span>
                      </div>
                    )}
                    {current.if_fail && (
                      <div className="branching-row">
                        <span className="branching-key branching-key--fail">fail</span>
                        <span>{current.if_fail}</span>
                      </div>
                    )}
                    {current.if_ignore && (
                      <div className="branching-row">
                        <span className="branching-key branching-key--ignore">ignore</span>
                        <span>{current.if_ignore}</span>
                      </div>
                    )}
                    {current.if_short && (
                      <div className="branching-row">
                        <span className="branching-key branching-key--short">short</span>
                        <span>{current.if_short}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="field" style={{ gap: 9 }}>
                <span className="field-label">CLUES IN PLAY</span>
                {clues.length > 0 ? (
                  clues.map((clue) => (
                    <div className="clue-row" key={clue.tier}>
                      <TierBadge tier={clue.tier} />
                      <span className="clue-text" style={{ fontSize: 13 }}>
                        {clue.text}
                      </span>
                    </div>
                  ))
                ) : (
                  <span className="drawer-empty">No clues tied to this scene.</span>
                )}
              </div>

              <div className="wrap-generate" style={{ gap: 8 }}>
                <span className="field-label">QUICK NOTE</span>
                <textarea
                  className="textarea"
                  placeholder="Type anything worth remembering — feeds into wrap capture after the session."
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                {note.trim() && (
                  <button
                    className="btn-ghost"
                    style={{ width: "fit-content" }}
                    disabled={patchSession.isPending}
                    onClick={saveNote}
                  >
                    {patchSession.isPending ? "Saving…" : "Save note"}
                  </button>
                )}
              </div>

              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                <button className="btn-block" style={{ flex: "none", padding: "10px 20px" }} onClick={advance}>
                  Next scene →
                </button>
                {floating.length > 0 && (
                  <button className="btn-ghost" onClick={() => setCurrentId(floating[0].id)}>
                    Jump to floating
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              Spine complete — head to wrap capture when the table winds down.
            </div>
          )}
        </section>

        {/* right: live clocks + pinned + rolls */}
        <aside className="run-right">
          <div className="field" style={{ gap: 12 }}>
            <span className="drawer-section-label">LIVE CLOCKS</span>
            {clocks.length === 0 && <span className="drawer-empty">No active clocks.</span>}
            {clocks.map((clock) => {
              const angle = clock.segments > 0 ? (clock.filled / clock.segments) * 360 : 0;
              const color = clock.kind === "countdown" ? "var(--amber-bright)" : "var(--teal)";
              return (
                <div className="live-clock-card" key={clock.id}>
                  <div className="live-clock-top">
                    <div
                      className="clock-mid-ring"
                      style={{
                        width: 52,
                        height: 52,
                        background: `conic-gradient(${color} 0deg ${angle}deg, var(--surface-raised) ${angle}deg 360deg)`,
                      }}
                    >
                      <div className="clock-mid-ring-inner" style={{ width: 38, height: 38, fontSize: 11, color }}>
                        {clock.filled}/{clock.segments}
                      </div>
                    </div>
                    <span className="clock-card-name" style={{ fontSize: 13 }}>
                      {clock.name}
                    </span>
                  </div>
                  <div className="live-clock-btns">
                    <button
                      className="btn btn-primary"
                      style={{ padding: "4px 12px", fontSize: 12 }}
                      disabled={tick.isPending}
                      onClick={() => tickClock(clock.id, 1)}
                    >
                      +1
                    </button>
                    <button
                      className="btn-ghost"
                      style={{ padding: "4px 12px", fontSize: 12 }}
                      disabled={tick.isPending}
                      onClick={() => tickClock(clock.id, -1)}
                    >
                      −1
                    </button>
                  </div>
                </div>
              );
            })}
            <span className="field-hint">
              Ticks here write instantly and may trigger cascades — a toast confirms what else
              moved.
            </span>
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">PINNED — THIS SCENE</span>
            {current && current.pinned_material.length > 0 ? (
              current.pinned_material.map((pin) => (
                <div className="pinned-row" key={pin.path}>
                  <div className="pinned-thumb" />
                  <div className="pinned-meta">
                    <span className="pinned-name">{pin.title || pin.path}</span>
                    <span className="pinned-path">{pin.path}</span>
                  </div>
                </div>
              ))
            ) : (
              <span className="drawer-empty">
                Nothing pinned to {current ? `"${current.title}."` : "this scene."}
              </span>
            )}
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">QUICK ROLL</span>
            <div style={{ display: "flex", gap: 8 }}>
              {rollTables.map((table) => (
                <button
                  key={table.key}
                  className="btn-ghost"
                  style={{ flex: 1, padding: "8px 0", fontSize: 12.5 }}
                  disabled={roll.isPending}
                  onClick={() =>
                    roll.mutate(table.key, {
                      onSuccess: (entry) =>
                        showToast(`${table.label}: ${entry.name}${entry.description ? ` — ${entry.description}` : ""}`),
                    })
                  }
                >
                  {table.label}
                </button>
              ))}
              {rollTables.length === 0 && <span className="drawer-empty">No tables seeded.</span>}
            </div>
          </div>
        </aside>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
