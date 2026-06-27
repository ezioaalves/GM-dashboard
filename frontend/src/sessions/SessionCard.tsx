import { usePatchSessionStatus } from "../api/sessions";
import type { Session } from "../types/session";

const SESSION_STATUSES = ["Planned", "Active", "Played"] as const;

const STATUS_COLORS: Record<string, string> = {
  Planned: "var(--color-text-muted)",
  Active: "var(--color-accent)",
  Played: "var(--color-text-secondary)",
};

interface SessionCardProps {
  session: Session;
  onClick?: () => void;
  isSelected?: boolean;
  sceneCount?: number;
}

export function SessionCard({ session, onClick, isSelected, sceneCount }: SessionCardProps) {
  const patchStatus = usePatchSessionStatus();
  const snippet = (session.notes || "").slice(0, 90);
  const truncated = (session.notes || "").length > 90;

  async function handleStatusClick(e: React.MouseEvent) {
    e.stopPropagation();
    const currentIndex = SESSION_STATUSES.indexOf(session.status as typeof SESSION_STATUSES[number]);
    const nextStatus = SESSION_STATUSES[(currentIndex + 1) % SESSION_STATUSES.length];
    await patchStatus.mutateAsync({ id: session.id, status: nextStatus });
  }

  return (
    <>
      <div className="deck-card-badges">
        <span className="tag">Session {session.number}</span>
        <span
          className="session-card__status-badge"
          style={{ color: STATUS_COLORS[session.status] }}
          onClick={handleStatusClick}
          title="Click to advance status"
        >
          {session.status}
        </span>
      </div>
      <div className="deck-card-title">{session.name || "Untitled Session"}</div>
      <div className="session-card-meta">
        <span>{session.date || "No date"}</span>
        <span>{session.scene_count} scene{session.scene_count === 1 ? "" : "s"}</span>
      </div>
      {snippet && (
        <div className="deck-card-snippet">
          {snippet}{truncated ? "…" : ""}
        </div>
      )}
    </>
  );
}
