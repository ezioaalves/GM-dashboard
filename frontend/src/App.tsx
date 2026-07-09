import { useState } from "react";
import { AppShell } from "./components/AppShell";
import { Sidebar, type PageKey } from "./components/Sidebar";
import { Cockpit } from "./pages/Cockpit";
import { Placeholder } from "./pages/Placeholder";
import { useAttentionItems } from "./hooks/useAttentionItems";
import { useSyncFreshnessQuery } from "./api/sync";
import { useRisksStaleQuery } from "./api/risks";
import { useFoundryStatusQuery } from "./api/cockpit";
import { useSessionsQuery } from "./api/sessions";
import type { Session } from "./types/session";

const PAGE_TITLES: Record<Exclude<PageKey, "cockpit">, string> = {
  adventures: "Adventures",
  sessions: "Sessions",
  "scene-deck": "Scene Deck",
  generator: "Generator",
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

  const attentionItems = useAttentionItems();
  const { data: freshness } = useSyncFreshnessQuery();
  const { data: staleRisks = [] } = useRisksStaleQuery();
  const { data: foundryStatus } = useFoundryStatusQuery();
  const { data: sessions } = useSessionsQuery();

  const nextSession = pickNextSession(sessions);
  const syncBadge = (freshness?.counts.pending_reviews ?? 0) + (freshness?.counts.conflict_reviews ?? 0);

  return (
    <AppShell
      sidebar={
        <Sidebar
          current={page}
          onNavigate={setPage}
          attentionCount={attentionItems.length}
          syncBadge={syncBadge}
          risksBadge={staleRisks.length}
          foundryStatus={foundryStatus}
          nextSessionLabel={nextSession ? `Session ${nextSession.number} · ${nextSession.status}` : "No session queued"}
        />
      }
    >
      {page === "cockpit" ? (
        <Cockpit onNavigate={setPage} />
      ) : (
        <Placeholder title={PAGE_TITLES[page]} />
      )}
    </AppShell>
  );
}
