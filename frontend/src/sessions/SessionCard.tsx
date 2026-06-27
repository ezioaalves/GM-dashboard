import type { Session } from "../types/session";

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
  const snippet = (session.notes || "").slice(0, 90);
  const truncated = (session.notes || "").length > 90;

  return (
    <>
      <div className="deck-card-badges">
        <span className="tag">Session {session.number}</span>
        <span className="tag" style={{ color: STATUS_COLORS[session.status] }}>
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
