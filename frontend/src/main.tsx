import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Link, Search, ShieldCheck, X } from "lucide-react";
import KanbanBoard from "./tickets/KanbanBoard";
import SceneDeck from "./scenes/SceneDeck";
import SessionDeck from "./sessions/SessionDeck";
import AdventureDeck from "./adventures/AdventureDeck";
import SessionNote from "./SessionNote";
import ThreadDirectionDashboard from "./threads/ThreadDirectionDashboard";
import ClocksPage from "./clocks/ClocksPage";
import { AppShell } from "./components/AppShell";
import { Sidebar } from "./components/Sidebar";
import { ClockStrip } from "./components/ClockStrip";
import { useSyncFreshnessQuery } from "./api/sync";
import SyncCenter from "./sync/SyncCenter";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function stateClass(state) {
  return state === "fresh" || state === "configured"
    ? "ok"
    : state === "missing" || state === "error" || state === "conflict" || state === "failed"
    ? "bad"
    : "warn";
}

function App() {
  const [data, setData] = useState<any>(null);
  const [activeTool, setActiveTool] = useState("session-deck");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [foundry, setFoundry] = useState(null);
  const [openFile, setOpenFile] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const { data: syncFreshness } = useSyncFreshnessQuery();

  function handleSelectSession(id: number) {
    setSelectedSessionId((prev) => (prev === id ? null : id));
  }

  useEffect(() => {
    fetch("/api/cockpit/session")
      .then((r) => r.json())
      .then(setData)
      .catch((err) => setError(`Could not load cockpit: ${err.message}`));
  }, []);

  async function runSearch() {
    await runAction("Searching vault...", async () => {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=12`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setSearchResults(json);
      setStatus(`Found ${json.length} result${json.length === 1 ? "" : "s"} for "${query}".`);
    });
  }

  async function loadFoundry() {
    await runAction("Checking Foundry status...", async () => {
      const res = await fetch("/api/foundry/status");
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setFoundry(json);
      setStatus(`Foundry status: ${json.state}.`);
    });
  }

  async function openMarkdown(path) {
    await runAction(`Opening ${path}...`, async () => {
      const res = await fetch(`/api/files/markdown?path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setOpenFile(json);
      setStatus(`Opened ${json.path}.`);
    });
  }

  async function runAction(message, fn) {
    setError("");
    setStatus(message);
    try {
      await fn();
    } catch (err) {
      setError(err.message || String(err));
      setStatus("");
    }
  }

  function openTool(tool) {
    setActiveTool(tool);
    setError("");
    setStatus("");
    if (tool === "foundry" && !foundry) loadFoundry();
  }

  if (!data) return <main className="shell"><p>Loading cockpit...</p></main>;

  const sessionDisplayName = data ? `Session ${data.latest_session.session}` : "—";

  return (
    <AppShell
      sidebar={
        <Sidebar
          activeTool={activeTool}
          onToolChange={openTool}
          sessionName={sessionDisplayName}
          syncPendingCount={
            (syncFreshness?.counts.pending_reviews ?? 0) +
            (syncFreshness?.counts.conflict_reviews ?? 0)
          }
        />
      }
    >
      <div className="main-workbench">
        <section className="badges">
          <span className={`badge badge--${stateClass(syncFreshness?.state ?? "pending")}`}>
            <ShieldCheck size={14} /> sync: {syncFreshness?.state ?? "loading"}
          </span>
        </section>

        {syncFreshness && (syncFreshness.state === "conflict" || syncFreshness.state === "failed") && (
          <section className="notice bad">
            <span>
              {syncFreshness.items.filter((item) => item.priority === "high").length} high-priority
              sync issue(s) need attention.
            </span>
            <button onClick={() => openTool("sync-center")}>Open Sync Center</button>
          </section>
        )}

        <ClockStrip onOpenClocks={() => openTool("clocks")} />

        {(status || error) && (
          <section className={`notice ${error ? "bad" : "ok"}`}>
            <span>{error || status}</span>
            <button aria-label="Dismiss" onClick={() => { setStatus(""); setError(""); }}>
              <X size={14} />
            </button>
          </section>
        )}

        <section className="workbench">
          {activeTool === "session-note" && (
            <SessionNote
              onStatusChange={setStatus}
              runAction={runAction}
            />
          )}
          {activeTool === "scene-deck" && (
            <SceneDeck
              selectedSessionId={selectedSessionId}
              onStatusChange={setStatus}
              onErrorChange={setError}
              runAction={runAction}
            />
          )}
          {activeTool === "session-deck" && (
            <SessionDeck
              selectedSessionId={selectedSessionId}
              onSelectSession={handleSelectSession}
              onStatusChange={setStatus}
              onErrorChange={setError}
              runAction={runAction}
            />
          )}
          {activeTool === "adventure-deck" && <AdventureDeck />}
          {activeTool === "threads" && (
            <ThreadDirectionDashboard
              onStatusChange={setStatus}
              onErrorChange={setError}
            />
          )}
          {activeTool === "clocks" && <ClocksPage />}
          {activeTool === "search" && (
            <div className="toolPanel">
              <div className="panelHeader">
                <div>
                  <h2>Search Vault</h2>
                  <p>Simple Markdown search across Campaign Management, Lore, and Mechanics.</p>
                </div>
                <button onClick={runSearch}>
                  <Search size={16} /> Search
                </button>
              </div>
              <label className="field">
                <span>Query</span>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
                />
              </label>
              <div className="results">
                {searchResults.map((row) => (
                  <article className="card" key={row.path}>
                    <h3>{row.title}</h3>
                    <p>{row.snippet}</p>
                    <code>{row.path}</code>
                    <button className="cardAction" onClick={() => openMarkdown(row.path)}>
                      Open Markdown
                    </button>
                  </article>
                ))}
              </div>
            </div>
          )}
          {activeTool === "tickets" && (
            <div className="toolPanel">
              <div className="panelHeader">
                <div>
                  <h2>Operational Tickets</h2>
                  <p>Drag cards between lanes to update stage. Click a card to edit.</p>
                </div>
              </div>
              <KanbanBoard />
            </div>
          )}
          {activeTool === "sync-center" && <SyncCenter />}
          {activeTool === "foundry" && (
            <div className="toolPanel">
              <div className="panelHeader">
                <div>
                  <h2>Foundry Link</h2>
                  <p>Status only for now. Sync stays behind a future diff/approval gate.</p>
                </div>
                <button onClick={loadFoundry}>
                  <Link size={16} /> Check Status
                </button>
              </div>
              {foundry && <pre className="resultBlock">{JSON.stringify(foundry, null, 2)}</pre>}
            </div>
          )}
        </section>

        {openFile && (
          <div className="modalBackdrop">
            <section className="markdownModal">
              <header className="modalHeader">
                <div>
                  <h2>Markdown Editor</h2>
                  <p>Read-only context. Canonical writes go through draft preview and confirm flows.</p>
                  <code>{openFile.path}</code>
                </div>
                <div className="modalActions">
                  <button onClick={() => setOpenFile(null)}><X size={16} /> Close</button>
                </div>
              </header>
              <pre>{openFile.markdown}</pre>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default App;

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
