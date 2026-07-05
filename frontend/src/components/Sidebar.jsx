import { CalendarDays, GitBranch, LayoutGrid, Search, FileDiff, Link, Timer } from "lucide-react";

const TOOLS = [
  { key: "session-deck", label: "Session Deck", icon: CalendarDays },
  { key: "scene-deck", label: "Scene Deck", icon: LayoutGrid },
  { key: "threads", label: "Thread Direction", icon: GitBranch },
  { key: "clocks", label: "Clocks", icon: Timer },
  { key: "search", label: "Search Vault", icon: Search },
  { key: "tickets", label: "Tickets", icon: FileDiff },
  { key: "foundry", label: "Foundry Link", icon: Link },
];

export function Sidebar({ activeTool, onToolChange, sessionName }) {
  return (
    <div className="sidebar-container">
      {/* App Identity */}
      <div className="sidebar-identity">
        <div className="app-mark">𝐊</div>
        <div className="app-title">
          <div className="app-name">Kaihou</div>
          <div className="app-subtitle">GM Dashboard</div>
        </div>
      </div>

      {/* Tool Navigation */}
      <nav className="sidebar-nav">
        {TOOLS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`nav-item ${activeTool === key ? "active" : ""}`}
            onClick={() => onToolChange(key)}
            title={label}
          >
            <Icon size={18} />
            <span className="nav-label">{label}</span>
          </button>
        ))}
      </nav>

      {/* Session Context */}
      <div className="sidebar-session">
        <div className="session-label">Active Session</div>
        <div className="session-name">{sessionName}</div>
      </div>
    </div>
  );
}
