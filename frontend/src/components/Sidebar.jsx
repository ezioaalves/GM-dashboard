import {
  CalendarDays, GitBranch, LayoutGrid, Search, FileDiff, Link, Timer, BookOpen, RefreshCw,
  Users, ShieldAlert, MessageSquare,
} from "lucide-react";

const TOOLS = [
  { key: "session-deck", label: "Session Deck", icon: CalendarDays },
  { key: "adventure-deck", label: "Adventures", icon: BookOpen },
  { key: "scene-deck", label: "Scene Deck", icon: LayoutGrid },
  { key: "threads", label: "Thread Direction", icon: GitBranch },
  { key: "clocks", label: "Clocks", icon: Timer },
  { key: "pc-lanes", label: "PC Lanes", icon: Users },
  { key: "risk-register", label: "Risk Register", icon: ShieldAlert },
  { key: "feedback-tracker", label: "Feedback", icon: MessageSquare },
  { key: "search", label: "Search Vault", icon: Search },
  { key: "tickets", label: "Tickets", icon: FileDiff },
  { key: "sync-center", label: "Sync Center", icon: RefreshCw },
  { key: "foundry", label: "Foundry Link", icon: Link },
];

export function Sidebar({ activeTool, onToolChange, sessionName, syncPendingCount = 0, campaignAlertCount = 0 }) {
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
            {key === "sync-center" && syncPendingCount > 0 && (
              <span className="sync-group-count">{syncPendingCount}</span>
            )}
            {key === "risk-register" && campaignAlertCount > 0 && (
              <span className="sync-group-count">{campaignAlertCount}</span>
            )}
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
