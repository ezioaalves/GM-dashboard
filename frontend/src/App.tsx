import { useState } from "react";
import { AppShell } from "./components/AppShell";
import { Sidebar, type PageKey } from "./components/Sidebar";
import { Cockpit } from "./pages/Cockpit";
import { SessionPlanner } from "./pages/SessionPlanner";
import { SceneDeck } from "./pages/SceneDeck";
import { Adventures } from "./pages/Adventures";
import { ClockBoard } from "./pages/ClockBoard";
import { SyncCenter } from "./pages/SyncCenter";
import { Tickets } from "./pages/Tickets";
import { CampaignHealth } from "./pages/CampaignHealth";
import { RunMode } from "./pages/RunMode";
import { Library } from "./pages/Library";
import { AssetsSearch } from "./pages/AssetsSearch";
import { GeneratorPanel } from "./components/GeneratorPanel";
import { Placeholder } from "./pages/Placeholder";
import { useAttentionItems } from "./hooks/useAttentionItems";
import { useSyncFreshnessQuery } from "./api/sync";
import { useRisksStaleQuery } from "./api/risks";
import { useFoundryStatusQuery } from "./api/cockpit";
import { useSessionsQuery } from "./api/sessions";
import type { Session } from "./types/session";

// "generator" is intercepted in navigate() and never becomes the page state.
const PAGE_TITLES: Record<Exclude<PageKey, "cockpit" | "generator">, string> = {
  adventures: "Adventures",
  sessions: "Sessions",
  "scene-deck": "Scene Deck",
  threads: "Threads",
  "pc-lanes": "PC Lanes",
  risks: "Risk Register",
  feedback: "Feedback",
  "sync-center": "Sync Center",
  clocks: "Clocks",
  tickets: "Tickets",
  lore: "Lore",
  npcs: "NPCs",
  pcs: "PCs",
  "library-search": "Assets · Search",
  "run-mode": "Run Mode",
};

function pickNextSession(sessions: Session[] | undefined): Session | null {
  if (!sessions) return null;
  const upcoming = sessions.filter((s) => s.status === "planned" || s.status === "ready");
  if (upcoming.length === 0) return null;
  return [...upcoming].sort((a, b) => a.number - b.number)[0];
}

export function App() {
  const [page, setPage] = useState<PageKey>("cockpit");
  const [genOpen, setGenOpen] = useState(false);

  // The Generator is an overlay panel, not a page — intercept its nav item.
  function navigate(next: PageKey) {
    if (next === "generator") {
      setGenOpen(true);
      return;
    }
    setPage(next);
  }

  const attentionItems = useAttentionItems();
  const { data: freshness } = useSyncFreshnessQuery();
  const { data: staleRisks = [] } = useRisksStaleQuery();
  const { data: foundryStatus } = useFoundryStatusQuery();
  const { data: sessions } = useSessionsQuery();

  const nextSession = pickNextSession(sessions);
  const syncBadge = (freshness?.counts.pending_reviews ?? 0) + (freshness?.counts.conflict_reviews ?? 0);

  // Run mode takes over the full screen — it is not a sidebar page.
  if (page === "run-mode") {
    return <RunMode onExit={() => setPage("cockpit")} />;
  }

  return (
    <AppShell
      sidebar={
        <Sidebar
          current={page}
          onNavigate={navigate}
          attentionCount={attentionItems.length}
          syncBadge={syncBadge}
          risksBadge={staleRisks.length}
          foundryStatus={foundryStatus}
          nextSessionLabel={nextSession ? `Session ${nextSession.number} · ${nextSession.status}` : "No session queued"}
        />
      }
    >
      {page === "cockpit" ? (
        <Cockpit onNavigate={navigate} />
      ) : page === "sessions" ? (
        <SessionPlanner />
      ) : page === "scene-deck" ? (
        <SceneDeck onNavigate={navigate} />
      ) : page === "adventures" ? (
        <Adventures />
      ) : page === "clocks" ? (
        <ClockBoard />
      ) : page === "sync-center" ? (
        <SyncCenter />
      ) : page === "tickets" ? (
        <Tickets onNavigate={navigate} />
      ) : page === "threads" || page === "pc-lanes" || page === "risks" || page === "feedback" ? (
        <CampaignHealth />
      ) : page === "lore" || page === "npcs" || page === "pcs" ? (
        <Library onNavigate={navigate} />
      ) : page === "library-search" ? (
        <AssetsSearch onNavigate={navigate} />
      ) : (
        <Placeholder title={PAGE_TITLES[page as Exclude<PageKey, "cockpit" | "generator">]} />
      )}
      {genOpen && <GeneratorPanel onClose={() => setGenOpen(false)} />}
    </AppShell>
  );
}
