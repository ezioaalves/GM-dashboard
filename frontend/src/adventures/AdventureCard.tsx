import type { Adventure } from "../types/adventure";

interface Props {
  adventure: Adventure;
  onClick: () => void;
}

export default function AdventureCard({ adventure, onClick }: Props) {
  return (
    <button className="adventure-card" onClick={onClick}>
      <div className="adventure-card-header">
        <span className={`adventure-status-badge status-${adventure.status}`}>{adventure.status}</span>
        {adventure.mode && <span className="adventure-mode-badge">{adventure.mode}</span>}
      </div>
      <div className="adventure-card-title">{adventure.title || "Untitled Adventure"}</div>
      {adventure.pitch && <p className="adventure-card-pitch">{adventure.pitch}</p>}
      <div className="adventure-card-meta">
        {adventure.current_arc && <span>{adventure.current_arc}</span>}
        <span>{adventure.session_count} session{adventure.session_count === 1 ? "" : "s"}</span>
      </div>
    </button>
  );
}
