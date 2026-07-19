import { useState } from "react";
import { AppShell } from "./components/AppShell";
import { Sidebar } from "./components/Sidebar";
import { pageRegistry, renderPage, type PageKey } from "./navigation";
import { useAttentionItems } from "./hooks/useAttentionItems";
import { useSyncFreshnessQuery } from "./api/sync";
import { useRisksStaleQuery } from "./api/risks";
import { useFoundryStatusQuery } from "./api/cockpit";
import { useSessionsQuery } from "./api/sessions";
import type { Session } from "./types/session";

function pickNextSession(sessions: Session[] | undefined): Session | null { const upcoming = sessions?.filter((session) => session.status === "planned" || session.status === "ready") ?? []; return upcoming.length ? [...upcoming].sort((left, right) => left.number - right.number)[0] : null; }
export function App() {
  const [page, setPage] = useState<PageKey>("cockpit"); const [overlay, setOverlay] = useState<PageKey | null>(null); const attentionItems = useAttentionItems(); const { data: freshness } = useSyncFreshnessQuery(); const { data: staleRisks = [] } = useRisksStaleQuery(); const { data: foundryStatus } = useFoundryStatusQuery(); const { data: sessions } = useSessionsQuery();
  const navigate = (next: PageKey) => { if (pageRegistry[next].mode === "overlay") { setOverlay(next); return; } setPage(next); };
  const context = { navigate, closeOverlay: () => setOverlay(null) }; const nextSession = pickNextSession(sessions); const syncBadge = (freshness?.counts.pending_reviews ?? 0) + (freshness?.counts.conflict_reviews ?? 0);
  if (pageRegistry[page].mode === "fullscreen") return <>{renderPage(page, context)}</>;
  return <AppShell sidebar={<Sidebar current={page} onNavigate={navigate} attentionCount={attentionItems.length} syncBadge={syncBadge} risksBadge={staleRisks.length} foundryStatus={foundryStatus} nextSessionLabel={nextSession ? `Session ${nextSession.number} · ${nextSession.status}` : "No session queued"} />}>{renderPage(page, context)}{overlay && renderPage(overlay, context)}</AppShell>;
}
