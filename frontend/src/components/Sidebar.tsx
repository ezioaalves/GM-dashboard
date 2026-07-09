import type { FoundryStatus } from "../types/cockpit";

export type PageKey =
  | "cockpit"
  | "adventures"
  | "sessions"
  | "scene-deck"
  | "generator"
  | "threads"
  | "pc-lanes"
  | "risks"
  | "feedback"
  | "sync-center"
  | "clocks"
  | "tickets"
  | "lore"
  | "npcs"
  | "pcs"
  | "library-search"
  | "run-mode";

interface NavItem {
  key: PageKey;
  label: string;
  badge?: number;
  badgeKind?: "attention" | "info";
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

interface SidebarProps {
  current: PageKey;
  onNavigate: (page: PageKey) => void;
  attentionCount: number;
  syncBadge: number;
  risksBadge: number;
  foundryStatus?: FoundryStatus;
  nextSessionLabel: string;
}

export function Sidebar({
  current,
  onNavigate,
  attentionCount,
  syncBadge,
  risksBadge,
  foundryStatus,
  nextSessionLabel,
}: SidebarProps) {
  const groups: NavGroup[] = [
    {
      label: "PLAN",
      items: [
        { key: "adventures", label: "Adventures" },
        { key: "sessions", label: "Sessions" },
        { key: "scene-deck", label: "Scene Deck" },
        { key: "generator", label: "Generator" },
      ],
    },
    {
      label: "FOLLOW UP",
      items: [
        { key: "threads", label: "Threads" },
        { key: "pc-lanes", label: "PC Lanes" },
        { key: "risks", label: "Risks", badge: risksBadge, badgeKind: "info" },
        { key: "feedback", label: "Feedback" },
      ],
    },
    {
      label: "MAINTAIN",
      items: [
        { key: "sync-center", label: "Sync Center", badge: syncBadge, badgeKind: "attention" },
        { key: "clocks", label: "Clocks" },
        { key: "tickets", label: "Tickets" },
      ],
    },
    {
      label: "LIBRARY",
      items: [
        { key: "lore", label: "Lore" },
        { key: "npcs", label: "NPCs" },
        { key: "pcs", label: "PCs" },
        { key: "library-search", label: "Assets · Search" },
      ],
    },
  ];

  const configured = foundryStatus?.state === "configured";

  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark" />
        <span className="sidebar-brand-name">Kaihou</span>
      </div>

      <button
        className={`sidebar-item${current === "cockpit" ? " active" : ""}`}
        onClick={() => onNavigate("cockpit")}
      >
        <span>Cockpit</span>
        {attentionCount > 0 && <span className="sidebar-badge sidebar-badge--attention">{attentionCount}</span>}
      </button>

      {groups.map((group) => (
        <div key={group.label}>
          <div className="sidebar-group-label">{group.label}</div>
          {group.items.map((item) => (
            <button
              key={item.key}
              className={`sidebar-item${current === item.key ? " active" : ""}`}
              onClick={() => onNavigate(item.key)}
            >
              <span>{item.label}</span>
              {!!item.badge && (
                <span className={`sidebar-badge sidebar-badge--${item.badgeKind ?? "info"}`}>{item.badge}</span>
              )}
            </button>
          ))}
        </div>
      ))}

      <div className="sidebar-footer">
        <div className="sidebar-foundry">
          <span className={`sidebar-foundry-dot sidebar-foundry-dot--${configured ? "on" : "off"}`} />
          Foundry · {configured ? "configured" : "not configured"}
        </div>
        <div className="sidebar-session-cta" onClick={() => onNavigate("run-mode")}>
          <span className="sidebar-session-cta-label">{nextSessionLabel}</span>
          <span className="sidebar-session-cta-action">RUN →</span>
        </div>
      </div>
    </nav>
  );
}
