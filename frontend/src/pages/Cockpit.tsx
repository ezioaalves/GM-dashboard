import type { PageKey } from "../components/Sidebar";
import { SeverityBadge, TagPill } from "../components/Badge";
import { ClockRing } from "../components/ClockRing";
import { useAttentionItems } from "../hooks/useAttentionItems";
import { useCockpitSessionQuery, useCockpitThreadDirectionQuery } from "../api/cockpit";
import { useSessionsQuery } from "../api/sessions";
import { useClocksQuery } from "../api/clocks";
import type { Session } from "../types/session";

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

function pickNextSession(sessions: Session[] | undefined): Session | null {
  if (!sessions) return null;
  const upcoming = sessions.filter((s) => s.status === "planned" || s.status === "ready");
  if (upcoming.length === 0) return null;
  return [...upcoming].sort((a, b) => a.number - b.number)[0];
}

export function Cockpit({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const items = useAttentionItems();
  const { data: cockpit } = useCockpitSessionQuery();
  const { data: threadDirection } = useCockpitThreadDirectionQuery();
  const { data: sessions } = useSessionsQuery();
  const { data: activeClocks = [] } = useClocksQuery({ lifecycle: "active" });

  const nextSession = pickNextSession(sessions);
  const gameInDays = nextSession ? daysUntil(nextSession.date) : null;

  const today = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date());

  const conflictCount = items.filter((i) => i.severity === "conflict").length;

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Cockpit</h1>
          <span className="page-subtitle">
            {today}
            {gameInDays != null &&
              (gameInDays === 0
                ? " · next game today"
                : gameInDays > 0
                  ? ` · next game in ${gameInDays} day${gameInDays === 1 ? "" : "s"}`
                  : "")}
          </span>
        </div>
        <div className="header-actions">
          <div className="search-box">
            <kbd>⌘K</kbd>
            Search vault…
          </div>
          <button className="btn btn-primary" onClick={() => onNavigate("ideas")}>
            ＋ Quick Capture
          </button>
        </div>
      </header>

      <div className="cockpit-grid">
        <section className="column">
          {cockpit?.current_hierarchy && <div className="panel panel-highlight">
            <div className="panel-label">CURRENT CAMPAIGN POSITION</div>
            <div className="next-session-title">{cockpit.current_hierarchy.arc} → {cockpit.current_hierarchy.adventure}</div>
            <span className="attention-card-detail">Next: {cockpit.current_hierarchy.next_session}</span>
            {(cockpit.history_gaps?.length ?? 0) > 0 && <span className="attention-card-detail">History gap: session 18 needs GM reconstruction</span>}
          </div>}
          <div className="column-heading">
            <h2>NEEDS YOUR ATTENTION</h2>
            <span className="count">
              {items.length} item{items.length === 1 ? "" : "s"}
              {conflictCount > 0 ? ` · ${conflictCount} conflict${conflictCount === 1 ? "" : "s"}` : ""}
            </span>
          </div>

          {items.length === 0 && (
            <div className="empty-state">Nothing needs your attention right now.</div>
          )}

          {items.map((item) => (
            <div className={`attention-card attention-card--${item.severity}`} key={item.key}>
              <SeverityBadge severity={item.severity} />
              <div className="attention-card-body">
                <span className="attention-card-title">{item.title}</span>
                {item.detail && <span className="attention-card-detail">{item.detail}</span>}
                {item.tags && (
                  <div className="attention-card-tags">
                    {item.tags.map((tag) => (
                      <TagPill key={tag}>{tag}</TagPill>
                    ))}
                  </div>
                )}
              </div>
              <button className="attention-card-action" onClick={() => onNavigate(item.targetPage)}>
                {item.actionLabel}
              </button>
            </div>
          ))}
        </section>

        <aside className="column">
          <div className={`panel${nextSession ? " panel-highlight" : ""}`}>
            {nextSession ? (
              <>
                <div className="next-session-top">
                  <div className="panel-header">
                    <span className="panel-label">NEXT SESSION</span>
                    <SeverityBadge
                      severity={nextSession.status === "ready" ? "fresh" : "stale"}
                      label={nextSession.status.toUpperCase()}
                    />
                  </div>
                  <span className="next-session-title">
                    {nextSession.number} — {nextSession.name}
                  </span>
                  {nextSession.promise && (
                    <p className="next-session-promise">
                      <span className="next-session-promise-label">PROMISE</span>
                      <br />
                      {nextSession.promise}
                    </p>
                  )}
                </div>
                <div className="next-session-stats">
                  <span>
                    <strong>{nextSession.scene_count}</strong> scenes
                  </span>
                  <span>
                    <strong>{nextSession.adventures.length}</strong> adventures
                  </span>
                  {nextSession.recap_seed && <span>✓ recap seeded</span>}
                </div>
                <div className="next-session-actions">
                  <button className="btn-block" onClick={() => onNavigate("run-mode")}>
                    Enter Run mode
                  </button>
                  <button className="btn-ghost" onClick={() => onNavigate("sessions")}>
                    Open plan
                  </button>
                </div>
              </>
            ) : (
              <div className="next-session-top" style={{ paddingBottom: 16 }}>
                <span className="panel-label">NEXT SESSION</span>
                <span className="next-session-promise">No session is planned or ready yet.</span>
                <button className="btn-ghost" onClick={() => onNavigate("sessions")}>
                  Plan one
                </button>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-header">
              <span className="panel-label">THREAD DIRECTION</span>
              <span className="panel-link" onClick={() => onNavigate("threads")}>
                All threads →
              </span>
            </div>
            {threadDirection ? (
              <>
                <div className="stat-row">
                  <span>
                    <strong>{threadDirection.active}</strong> active
                  </span>
                  <span>
                    <strong>{threadDirection.stale}</strong> stale
                  </span>
                  <span>
                    <strong>{threadDirection.needs_direction}</strong> no direction
                  </span>
                  <span>
                    <strong>{threadDirection.high_priority}</strong> high
                  </span>
                </div>
                {threadDirection.next_moves.length > 0 && (
                  <div className="next-move-list">
                    {threadDirection.next_moves.slice(0, 3).map((thread) => (
                      <div className="next-move-item" key={thread.id}>
                        <span className="next-move-slug">{thread.id}</span>
                        <span className="next-move-text">Next: {thread.next_move}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <span className="attention-card-detail">Loading thread direction…</span>
            )}
          </div>

          <div className="panel">
            <div className="panel-header">
              <span className="panel-label">ACTIVE CLOCKS</span>
              <span className="panel-link" onClick={() => onNavigate("clocks")}>
                Clock board →
              </span>
            </div>
            {activeClocks.length > 0 ? (
              <div className="clock-row">
                {activeClocks.slice(0, 3).map((clock) => (
                  <ClockRing clock={clock} key={clock.id} />
                ))}
              </div>
            ) : (
              <span className="attention-card-detail">No active clocks yet.</span>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
