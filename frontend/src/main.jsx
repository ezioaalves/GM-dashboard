import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Eye, FileDiff, Link, NotebookPen, Plus, Save, Search, ShieldCheck, X } from "lucide-react";
import "./styles.css";

const columns = [
  ["now", "Now"],
  ["next", "Next"],
  ["scene_deck", "Scene Deck"],
  ["capture", "Capture"],
  ["follow_up", "Follow-up"],
];

function stateClass(state) {
  return state === "fresh" || state === "configured" ? "ok" : state === "missing" || state === "error" ? "bad" : "warn";
}

function App() {
  const [data, setData] = useState(null);
  const [activeTool, setActiveTool] = useState("session-note");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [memory, setMemory] = useState("");
  const [sessionDraft, setSessionDraft] = useState(null);
  const [draftText, setDraftText] = useState("");
  const [sessionTarget, setSessionTarget] = useState("");
  const [sessionSavePreview, setSessionSavePreview] = useState(null);
  const [scene, setScene] = useState({ title: "", purpose: "", cast: "", clue: "", clock: "", foundry_needs: "", notes: "" });
  const [sceneDraft, setSceneDraft] = useState(null);
  const [sceneText, setSceneText] = useState("");
  const [sceneTarget, setSceneTarget] = useState("");
  const [sceneSavePreview, setSceneSavePreview] = useState(null);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [foundry, setFoundry] = useState(null);
  const [openFile, setOpenFile] = useState(null);

  useEffect(() => {
    fetch("/api/cockpit/session")
      .then((r) => r.json())
      .then(setData)
      .catch((err) => setError(`Could not load cockpit: ${err.message}`));
  }, []);

  async function quickNote() {
    await runAction("Generating session draft...", async () => {
      const json = await postJson("/api/capture/session-note", { memory });
      setSessionDraft(json);
      setDraftText(json.markdown);
      setSessionTarget(json.default_target_path);
      setSessionSavePreview(null);
      setStatus(`Session draft written to ${json.path}`);
    });
  }

  async function quickScene() {
    await runAction("Creating scene draft...", async () => {
      const json = await postJson("/api/capture/scene", {
        title: scene.title || "Untitled Scene",
        purpose: scene.purpose,
        cast: splitList(scene.cast),
        clue: scene.clue,
        clock: scene.clock,
        foundry_needs: splitList(scene.foundry_needs),
        notes: scene.notes,
      });
      setSceneDraft(json);
      setSceneText(json.markdown);
      setSceneTarget(json.default_target_path);
      setSceneSavePreview(null);
      setStatus(`Scene draft written to ${json.path}`);
    });
  }

  async function runSearch() {
    await runAction("Searching vault...", async () => {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=12`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setSearchResults(json);
      setStatus(`Found ${json.length} result${json.length === 1 ? "" : "s"} for "${query}".`);
    });
  }

  async function loadTickets() {
    await runAction("Loading tickets...", async () => {
      const res = await fetch("/api/tickets");
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setTickets(json);
      setStatus(`Loaded ${json.length} operational tickets.`);
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

  async function previewDraft(draft, targetPath, markdown, setPreview) {
    if (!draft) return;
    await runAction(`Preparing diff for ${targetPath}...`, async () => {
      const json = await postJson(`/api/drafts/${draft.id}/preview`, { target_path: targetPath, markdown });
      setPreview(json);
      setStatus(`Preview ready for ${json.path}.`);
    });
  }

  async function saveDraft(draft, targetPath, markdown, setPreview) {
    if (!draft) return;
    await runAction(`Saving ${targetPath}...`, async () => {
      const json = await postJson(`/api/drafts/${draft.id}/save`, { target_path: targetPath, markdown, confirm: true });
      setPreview(json);
      setStatus(`Canonical Markdown saved to ${json.path}.`);
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
    if (tool === "tickets" && tickets.length === 0) loadTickets();
    if (tool === "foundry" && !foundry) loadFoundry();
  }

  if (!data) return <main className="shell"><p>Loading cockpit...</p></main>;

  const freshness = Object.entries(data.freshness);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Kaihou GM Cockpit</p>
          <h1>Session {data.latest_session.session}: {data.latest_session.title}</h1>
          <p className="leaveoff">{data.leave_off.detail}</p>
        </div>
        <div className="actions">
          <button className={activeTool === "session-note" ? "active" : ""} onClick={() => openTool("session-note")}><NotebookPen size={16} /> Quick Session Note</button>
          <button className={activeTool === "scene" ? "active" : ""} onClick={() => openTool("scene")}><Plus size={16} /> Quick Scene</button>
          <button className={activeTool === "search" ? "active" : ""} onClick={() => openTool("search")}><Search size={16} /> Search Vault</button>
          <button className={activeTool === "tickets" ? "active" : ""} onClick={() => openTool("tickets")}><FileDiff size={16} /> Tickets</button>
          <button className={activeTool === "foundry" ? "active" : ""} onClick={() => openTool("foundry")}><Link size={16} /> Foundry Link</button>
        </div>
      </header>

      <section className="badges">
        {freshness.map(([key, value]) => (
          <span className={`badge ${stateClass(value.state)}`} key={key}>
            <ShieldCheck size={14} /> {key.replaceAll("_", " ")}: {value.state}
          </span>
        ))}
      </section>

      {(status || error) && (
        <section className={`notice ${error ? "bad" : "ok"}`}>
          <span>{error || status}</span>
          <button aria-label="Dismiss" onClick={() => { setStatus(""); setError(""); }}><X size={14} /></button>
        </section>
      )}

      <section className="workbench">
        {activeTool === "session-note" && (
          <div className="toolPanel">
            <div className="panelHeader">
              <div>
                <h2>Quick Session Note</h2>
                <p>Memory plus the latest session context becomes an editable Markdown draft.</p>
              </div>
              <button onClick={quickNote}><NotebookPen size={16} /> Generate Draft</button>
            </div>
            <div className="sessionGrid">
              <label className="field sourceBox">
                <span>Source</span>
                <pre>Latest: Session {data.latest_session.session} - {data.latest_session.title}

Leave-off: {data.leave_off.detail}

Path: {data.latest_session.path}</pre>
              </label>
              <label className="field memoryBox">
                <span>GM Memory</span>
                <textarea value={memory} onChange={(e) => setMemory(e.target.value)} placeholder="Drop rough memory here. Bullet fragments are fine." />
              </label>
            </div>
            {sessionDraft && (
              <div className="draftGrid wide">
                <label className="field">
                  <span>Editable Markdown Draft - {sessionDraft.path}</span>
                  <textarea value={draftText} onChange={(e) => setDraftText(e.target.value)} />
                </label>
                <label className="field">
                  <span>Preview</span>
                  <pre>{draftText}</pre>
                </label>
                <div className="saveFlow diffBox">
                  <Input label="Canonical target path" value={sessionTarget} onChange={setSessionTarget} />
                  <div className="saveActions">
                    <button onClick={() => previewDraft(sessionDraft, sessionTarget, draftText, setSessionSavePreview)}><Eye size={16} /> Preview Save</button>
                    <button onClick={() => saveDraft(sessionDraft, sessionTarget, draftText, setSessionSavePreview)}><Save size={16} /> Confirm Save</button>
                  </div>
                </div>
                <label className="field diffBox">
                  <span>{sessionSavePreview ? "Canonical Diff" : "Initial Draft Diff"}</span>
                  <pre>{(sessionSavePreview && sessionSavePreview.diff) || sessionDraft.diff}</pre>
                </label>
              </div>
            )}
          </div>
        )}

        {activeTool === "scene" && (
          <div className="toolPanel">
            <div className="panelHeader">
              <div>
                <h2>Quick Scene</h2>
                <p>Compact card for a runnable beat: purpose, cast, clue, clock, and Foundry needs.</p>
              </div>
              <button onClick={quickScene}><Plus size={16} /> Create Scene Draft</button>
            </div>
            <div className="formGrid">
              <Input label="Title" value={scene.title} onChange={(value) => setScene({ ...scene, title: value })} />
              <Input label="Cast" value={scene.cast} onChange={(value) => setScene({ ...scene, cast: value })} placeholder="Dan, Ikazuchi, Suigin" />
              <Input label="Purpose" value={scene.purpose} onChange={(value) => setScene({ ...scene, purpose: value })} />
              <Input label="Clock/thread" value={scene.clock} onChange={(value) => setScene({ ...scene, clock: value })} />
              <Input label="Clue" value={scene.clue} onChange={(value) => setScene({ ...scene, clue: value })} />
              <Input label="Foundry needs" value={scene.foundry_needs} onChange={(value) => setScene({ ...scene, foundry_needs: value })} placeholder="map, tokens, handout" />
              <label className="field spanAll">
                <span>Notes</span>
                <textarea value={scene.notes} onChange={(e) => setScene({ ...scene, notes: e.target.value })} />
              </label>
            </div>
            {sceneDraft && (
              <div className="draftGrid">
                <label className="field">
                  <span>Editable Scene Draft - {sceneDraft.path}</span>
                  <textarea value={sceneText} onChange={(e) => setSceneText(e.target.value)} />
                </label>
                <label className="field">
                  <span>Preview</span>
                  <pre>{sceneText}</pre>
                </label>
                <div className="saveFlow diffBox">
                  <Input label="Canonical target path" value={sceneTarget} onChange={setSceneTarget} />
                  <div className="saveActions">
                    <button onClick={() => previewDraft(sceneDraft, sceneTarget, sceneText, setSceneSavePreview)}><Eye size={16} /> Preview Save</button>
                    <button onClick={() => saveDraft(sceneDraft, sceneTarget, sceneText, setSceneSavePreview)}><Save size={16} /> Confirm Save</button>
                  </div>
                </div>
                {sceneSavePreview && (
                  <label className="field diffBox">
                    <span>Canonical Diff</span>
                    <pre>{sceneSavePreview.diff}</pre>
                  </label>
                )}
              </div>
            )}
          </div>
        )}

        {activeTool === "search" && (
          <div className="toolPanel">
            <div className="panelHeader">
              <div>
                <h2>Search Vault</h2>
                <p>Simple Markdown search across Campaign Management, Lore, and Mechanics.</p>
              </div>
              <button onClick={runSearch}><Search size={16} /> Search</button>
            </div>
            <label className="field">
              <span>Query</span>
              <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }} />
            </label>
            <div className="results">
              {searchResults.map((row) => (
                <article className="card" key={row.path}>
                  <h3>{row.title}</h3>
                  <p>{row.snippet}</p>
                  <code>{row.path}</code>
                  <button className="cardAction" onClick={() => openMarkdown(row.path)}>Open Markdown</button>
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
                <p>Current ticket view from Markdown frontmatter. New-ticket creation is still a next-step ticket.</p>
              </div>
              <button onClick={loadTickets}><FileDiff size={16} /> Refresh Tickets</button>
            </div>
            <div className="results">
              {tickets.map((ticket) => (
                <article className="card" key={ticket.id}>
                  <h3>{ticket.title}</h3>
                  <p>{ticket.next_action || ticket.resume_note || ticket.body_excerpt || "No next action set."}</p>
                  <code>{ticket.stage} / {ticket.status} / {ticket.path}</code>
                  <button className="cardAction" onClick={() => openMarkdown(ticket.path)}>Open Ticket</button>
                </article>
              ))}
            </div>
          </div>
        )}

        {activeTool === "foundry" && (
          <div className="toolPanel">
            <div className="panelHeader">
              <div>
                <h2>Foundry Link</h2>
                <p>Status only for now. Sync stays behind a future diff/approval gate.</p>
              </div>
              <button onClick={loadFoundry}><Link size={16} /> Check Status</button>
            </div>
            {foundry && <pre className="resultBlock">{JSON.stringify(foundry, null, 2)}</pre>}
          </div>
        )}
      </section>

      <section className="board">
        {columns.map(([key, label]) => (
          <div className="lane" key={key}>
            <h2>{label}</h2>
            {(data.columns[key] || []).map((card) => (
              <article className="card" key={card.id}>
                <h3>{card.title}</h3>
                <p>{card.detail || card.purpose || card.next_action || card.resume_note || card.body_excerpt}</p>
                {card.path && <code>{card.path}</code>}
              </article>
            ))}
          </div>
        ))}
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
    </main>
  );
}

export default App;

createRoot(document.getElementById("root")).render(<App />);

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function splitList(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function Input({ label, value, onChange, placeholder = "" }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
