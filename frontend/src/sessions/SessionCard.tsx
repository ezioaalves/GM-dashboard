import { usePatchSessionStatus } from "../api/sessions";
import type { Session, SessionStatus } from "../types/session";

const SESSION_STATUSES: SessionStatus[] = ["planned", "ready", "played", "cancelled", "archived"];

const STATUS_LABELS: Record<SessionStatus, string> = {
  planned: "Planned",
  ready: "Ready",
  played: "Played",
  cancelled: "Cancelled",
  archived: "Archived",
};

const STATUS_COLORS: Record<SessionStatus, string> = {
  planned: "var(--color-text-muted)",
  ready: "var(--color-accent)",
  played: "var(--color-text-secondary)",
  cancelled: "var(--color-text-muted)",
  archived: "var(--color-text-muted)",
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
    const currentIndex = SESSION_STATUSES.indexOf(session.status);
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
          {STATUS_LABELS[session.status]}
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
