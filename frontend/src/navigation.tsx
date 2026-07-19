import type { ReactNode } from "react";
import { Adventures } from "./pages/Adventures";
import { AssetsSearch } from "./pages/AssetsSearch";
import { CampaignHealth } from "./pages/CampaignHealth";
import { ClockBoard } from "./pages/ClockBoard";
import { Cockpit } from "./pages/Cockpit";
import { Ideas } from "./pages/Ideas";
import { Library } from "./pages/Library";
import { RunMode } from "./pages/RunMode";
import { SceneDeck } from "./pages/SceneDeck";
import { SessionPlanner } from "./pages/SessionPlanner";
import { SyncCenter } from "./pages/SyncCenter";
import { Tickets } from "./pages/Tickets";
import { GeneratorPanel } from "./components/GeneratorPanel";

type NavigationContext = { navigate: (page: PageKey) => void; closeOverlay: () => void };
export type NavGroup = "plan" | "follow-up" | "maintain" | "library";
export type BadgeKey = "attention" | "sync" | "risks";
type PageDefinition = { title: string; mode: "shell" | "overlay" | "fullscreen"; nav?: { group?: NavGroup; label: string; order?: number; badge?: BadgeKey; aliases?: string[] }; render: (context: NavigationContext) => ReactNode };

const definitions = {
  cockpit: { title: "Cockpit", mode: "shell", nav: { label: "Cockpit", badge: "attention" as BadgeKey }, render: (context: NavigationContext) => <Cockpit onNavigate={context.navigate} /> },
  adventures: { title: "Adventures", mode: "shell", nav: { group: "plan" as NavGroup, label: "Adventures", order: 1 }, render: () => <Adventures /> },
  ideas: { title: "Idea Inbox", mode: "shell", nav: { group: "plan" as NavGroup, label: "Idea Inbox", order: 2 }, render: () => <Ideas /> },
  sessions: { title: "Sessions", mode: "shell", nav: { group: "plan" as NavGroup, label: "Sessions", order: 3 }, render: () => <SessionPlanner /> },
  "scene-deck": { title: "Scene Deck", mode: "shell", nav: { group: "plan" as NavGroup, label: "Scene Deck", order: 4 }, render: (context: NavigationContext) => <SceneDeck onNavigate={context.navigate} /> },
  generator: { title: "Generator", mode: "overlay", nav: { group: "plan" as NavGroup, label: "Generator", order: 5 }, render: (context: NavigationContext) => <GeneratorPanel onClose={context.closeOverlay} /> },
  threads: { title: "Campaign Health", mode: "shell", nav: { group: "follow-up" as NavGroup, label: "Campaign Health", order: 1, badge: "risks" as BadgeKey, aliases: ["pc-lanes", "risks", "feedback"] }, render: () => <CampaignHealth /> },
  "pc-lanes": { title: "PC Lanes", mode: "shell", render: () => <CampaignHealth /> },
  risks: { title: "Risk Register", mode: "shell", render: () => <CampaignHealth /> },
  feedback: { title: "Feedback", mode: "shell", render: () => <CampaignHealth /> },
  "sync-center": { title: "Sync Center", mode: "shell", nav: { group: "maintain" as NavGroup, label: "Sync Center", order: 1, badge: "sync" as BadgeKey }, render: () => <SyncCenter /> },
  clocks: { title: "Clocks", mode: "shell", nav: { group: "maintain" as NavGroup, label: "Clocks", order: 2 }, render: () => <ClockBoard /> },
  tickets: { title: "Tickets", mode: "shell", nav: { group: "maintain" as NavGroup, label: "Tickets", order: 3 }, render: (context: NavigationContext) => <Tickets onNavigate={context.navigate} /> },
  lore: { title: "Library", mode: "shell", nav: { group: "library" as NavGroup, label: "Library", order: 1, aliases: ["npcs", "pcs"] }, render: (context: NavigationContext) => <Library onNavigate={context.navigate} /> },
  npcs: { title: "NPCs", mode: "shell", render: (context: NavigationContext) => <Library onNavigate={context.navigate} /> },
  pcs: { title: "PCs", mode: "shell", render: (context: NavigationContext) => <Library onNavigate={context.navigate} /> },
  "library-search": { title: "Assets · Search", mode: "shell", nav: { group: "library" as NavGroup, label: "Assets · Search", order: 2 }, render: (context: NavigationContext) => <AssetsSearch onNavigate={context.navigate} /> },
  "run-mode": { title: "Run Mode", mode: "fullscreen", render: (context: NavigationContext) => <RunMode onExit={() => context.navigate("cockpit")} /> },
} satisfies Record<string, PageDefinition>;

export type PageKey = keyof typeof definitions;
export const pageRegistry: Record<PageKey, PageDefinition> = definitions;
export const navGroups: { key: NavGroup; label: string }[] = [{ key: "plan", label: "PLAN" }, { key: "follow-up", label: "FOLLOW UP" }, { key: "maintain", label: "MAINTAIN" }, { key: "library", label: "LIBRARY" }];
export function renderPage(page: PageKey, context: NavigationContext): ReactNode { return pageRegistry[page].render(context); }
