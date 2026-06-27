import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Plus, Save, Trash, X, Search, Eye } from "lucide-react";
import CustomSelect from "../components/CustomSelect";

const SCENE_TYPES = [
  { value: "Hard", label: "Hard / Core" },
  { value: "Soft", label: "Soft / Supplemental" },
  { value: "Cut", label: "Cut" },
  { value: "Added", label: "Added" },
  { value: "Replacement", label: "Replacement" },
  { value: "Spotlight", label: "Spotlight" },
  { value: "Bridge", label: "Bridge" },
];

const STATUS_OPTIONS = [
  { value: "Draft", label: "Draft" },
  { value: "Ready", label: "Ready" },
  { value: "Played", label: "Played" },
  { value: "Cut", label: "Cut" },
];

function CreatableMultiTagSelect({ label, value, onChange, onCreateNew, placeholder, suggestions }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selected = new Set(value);
  const filtered = suggestions.filter(
    (s) => !selected.has(s) && s.toLowerCase().includes(query.toLowerCase())
  );
  const hasExactMatch =
    suggestions.some((s) => s.toLowerCase() === query.toLowerCase()) ||
    selected.has(query.trim());
  const canCreate = query.trim() && !hasExactMatch;

  function add(item) {
    onChange([...value, item]);
    setQuery("");
    inputRef.current?.focus();
  }

  return (
    <div className="field">
      <span>{label}</span>
      <div className="multi-tag-select" ref={ref}>
        <div
          className="multi-tag-input-row"
          onClick={() => { setOpen(true); inputRef.current?.focus(); }}
        >
          {value.map((v) => (
            <span key={v} className="tag">
              {v}
              <button
                type="button"
                className="tag-remove"
                onMouseDown={(e) => { e.stopPropagation(); onChange(value.filter((x) => x !== v)); }}
              >×</button>
            </span>
          ))}
          <input
            ref={inputRef}
            className="tag-input"
            value={query}
            placeholder={value.length === 0 ? placeholder : ""}
            onFocus={() => setOpen(true)}
            onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
            onKeyDown={(e) => {
              if (e.key === "Backspace" && !query && value.length) onChange(value.slice(0, -1));
            }}
          />
        </div>
        {open && (filtered.length > 0 || canCreate) && (
          <ul className="custom-select-dropdown">
            {filtered.map((item) => (
              <li key={item} className="custom-select-option" onMouseDown={() => add(item)}>{item}</li>
            ))}
            {canCreate && (
              <li className="custom-select-option custom-select-create"
                onMouseDown={() => { onCreateNew(query.trim()); setQuery(""); setOpen(false); }}>
                + Create "{query.trim()}"
              </li>
            )}
          </ul>
        )}
      </div>
    </div>
  );
}

function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details className="scene-section" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="scene-section-summary">
        <ChevronDown size={14} className={`scene-section-chevron${open ? " open" : ""}`} />
        {title}
      </summary>
      <div className="scene-section-body">{children}</div>
    </details>
  );
}

function PinsModal({ open, onClose, runAction, onStatusChange, onPin, pinnedPaths }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selectedPath, setSelectedPath] = useState(null);
  const [selectedContent, setSelectedContent] = useState("");

  async function pinSearch() {
    if (!query.trim()) return;
    await runAction("Searching vault...", async () => {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=20`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setResults(json);
      onStatusChange(`Found ${json.length} result${json.length === 1 ? "" : "s"}.`);
    });
  }

  async function viewContent(path) {
    await runAction(`Loading ${path}...`, async () => {
      const res = await fetch(`/api/files/markdown?path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setSelectedContent(json.markdown);
      setSelectedPath(path);
    });
  }

  function handlePin(result) {
    onPin(result);
    setResults(results.filter((r) => r.path !== result.path));
    setSelectedPath(null);
    setSelectedContent("");
  }

  if (!open) return null;

  return (
    <div className="modalBackdrop">
      <section className="markdownModal pins-modal">
        <header className="modalHeader">
          <div>
            <h2>Pin Material</h2>
            <p>Search the vault and pin NPCs, locations, or clues to this scene.</p>
          </div>
          <div className="modalActions">
            <button onClick={onClose}><X size={16} /> Close</button>
          </div>
        </header>
        <div className="pins-modal-body">
          <div className="pins-search-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search NPCs, locations, threads, clues…"
              onKeyDown={(e) => e.key === "Enter" && pinSearch()}
              className="pins-search-input"
            />
            <button onClick={pinSearch}><Search size={16} /> Search</button>
          </div>
          <div className="pins-results-pane">
            <div className="pins-list">
              {results.length === 0 && query ? (
                <p className="pins-empty">No results found.</p>
              ) : results.length === 0 ? (
                <p className="pins-empty">Type to search…</p>
              ) : (
                results.map((row) => {
                  const isPinned = pinnedPaths.includes(row.path);
                  return (
                    <div key={row.path}
                      className={`pins-result-card${selectedPath === row.path ? " selected" : ""}`}>
                      <div onClick={() => viewContent(row.path)} className="pins-result-meta">
                        <h4>{row.title}</h4>
                        <p>{row.snippet}</p>
                        <code>{row.path}</code>
                      </div>
                      <button onClick={() => handlePin(row)} disabled={isPinned}
                        className={isPinned ? "" : "active"}>
                        {isPinned ? "Already pinned" : "Pin"}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
            <div className="pins-preview">
              {selectedPath ? (
                <>
                  <div className="field"><span>{selectedPath}</span></div>
                  <pre>{selectedContent}</pre>
                </>
              ) : (
                <p className="pins-empty">Select a result to preview</p>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

const DEFAULT_SCENE = {
  title: "", type: "", status: "Draft", session_id: null, description: "",
  location: [], cast: [], clock: [], cuttable: false, purpose: "",
  pc_pressure: "", entry_pressure: "", exit_condition: "", core_clue: "",
  superior_clue: "", optional_clue: "", false_lead: "", opening_image: "",
  sensory_words: "", interactable_objects: "", rules_likely: "",
  foundry_needs: "", replacement_route: "", if_succeed: "", if_fail: "",
  if_ignore: "", if_short: "", notes: "", pinned_material: [],
};

export function SceneForm({ scene: initialScene, sessions, onSave, onDelete, runAction, onStatusChange }) {
  const [scene, setScene] = useState({ ...DEFAULT_SCENE, ...initialScene });
  const [pinnedMaterial, setPinnedMaterial] = useState(initialScene?.pinned_material || []);
  const [pinsModalOpen, setPinsModalOpen] = useState(false);
  const [sceneDraft, setSceneDraft] = useState(null);
  const [sceneText, setSceneText] = useState("");
  const [sceneTarget, setSceneTarget] = useState("");
  const [sceneSavePreview, setSceneSavePreview] = useState(null);

  const [castSuggestions, setCastSuggestions] = useState(["Dan", "Ikazuchi", "Suigin", "Kubo"]);
  const [locationSuggestions, setLocationSuggestions] = useState(["Iron Keep", "Kanigakure", "Training grounds", "Forest"]);
  const [clockSuggestions, setClockSuggestions] = useState(["Shadowlands escalation", "Exam countdown", "Clan pressure", "Mystery investigation"]);

  const sessionOptions = [
    { value: null, label: "— Backlog —" },
    ...sessions.map((s) => ({
      value: s.id,
      label: `Session ${s.number}${s.name ? ` — ${s.name}` : ""}`,
    })),
  ];

  function set(field) {
    return (val) => setScene((prev) => ({ ...prev, [field]: val }));
  }

  function setInput(field) {
    return (e) => setScene((prev) => ({ ...prev, [field]: e.target.value }));
  }

  function handleCreateNewCast(name) {
    setCastSuggestions((prev) => [...prev, name]);
    setScene((prev) => ({ ...prev, cast: [...prev.cast, name] }));
    onStatusChange(`Cast stub created: ${name}`);
  }

  function handleCreateNewLocation(name) {
    setLocationSuggestions((prev) => [...prev, name]);
    setScene((prev) => ({ ...prev, location: [...prev.location, name] }));
    onStatusChange(`Location stub created: ${name}`);
  }

  function handleCreateNewClock(name) {
    setClockSuggestions((prev) => [...prev, name]);
    setScene((prev) => ({ ...prev, clock: [...prev.clock, name] }));
    onStatusChange(`Clock stub created: ${name}`);
  }

  function pinItem(result) { setPinnedMaterial((prev) => [...prev, result]); }
  function unpinItem(path) { setPinnedMaterial((prev) => prev.filter((m) => m.path !== path)); }

  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function createDraft() {
    await runAction("Creating scene draft...", async () => {
      const json = await postJson("/api/capture/scene", {
        title: scene.title || "Untitled Scene",
        type: scene.type, cuttable: scene.cuttable, purpose: scene.purpose,
        pc_pressure: scene.pc_pressure, entry_pressure: scene.entry_pressure,
        exit_condition: scene.exit_condition, cast: scene.cast.join(", "),
        location: scene.location.join(", "), clock: scene.clock.join(", "),
        core_clue: scene.core_clue, superior_clue: scene.superior_clue,
        optional_clue: scene.optional_clue, false_lead: scene.false_lead,
        opening_image: scene.opening_image, sensory_words: scene.sensory_words,
        interactable_objects: scene.interactable_objects, rules_likely: scene.rules_likely,
        foundry_needs: scene.foundry_needs, replacement_route: scene.replacement_route,
        if_succeed: scene.if_succeed, if_fail: scene.if_fail,
        if_ignore: scene.if_ignore, if_short: scene.if_short,
        notes: scene.notes, pinned_material: pinnedMaterial,
      });
      setSceneDraft(json);
      setSceneText(json.markdown);
      setSceneTarget(json.default_target_path);
      setSceneSavePreview(null);
      onStatusChange(`Scene draft written to ${json.path}`);
    });
  }

  async function previewDraft() {
    if (!sceneDraft) return;
    await runAction(`Preparing diff for ${sceneTarget}...`, async () => {
      const json = await postJson(`/api/drafts/${sceneDraft.id}/preview`, { target_path: sceneTarget, markdown: sceneText });
      setSceneSavePreview(json);
      onStatusChange(`Preview ready for ${json.path}.`);
    });
  }

  async function saveDraftToVault() {
    if (!sceneDraft) return;
    await runAction(`Saving ${sceneTarget}...`, async () => {
      const json = await postJson(`/api/drafts/${sceneDraft.id}/save`, { target_path: sceneTarget, markdown: sceneText, confirm: true });
      setSceneSavePreview(json);
      onStatusChange(`Canonical Markdown saved to ${json.path}.`);
    });
  }

  async function handleSave() {
    await onSave({ ...scene, pinned_material: pinnedMaterial });
  }

  async function handleDelete() {
    if (scene.id) await onDelete(scene.id);
  }

  const pinnedPaths = pinnedMaterial.map((m) => m.path);

  return (
    <>
      {/* Header fields — always visible */}
      <div className="formGrid" style={{ marginBottom: "var(--space-4)" }}>
        <label className="field spanAll">
          <span>Title</span>
          <input value={scene.title} onChange={setInput("title")} placeholder="Scene name or hook" />
        </label>
        <label className="field">
          <span>Type</span>
          <CustomSelect value={scene.type} onChange={set("type")} options={SCENE_TYPES} placeholder="— Select —" />
        </label>
        <label className="field">
          <span>Status</span>
          <CustomSelect value={scene.status} onChange={set("status")} options={STATUS_OPTIONS} placeholder="— Select —" />
        </label>
        <label className="field">
          <span>Session</span>
          <CustomSelect value={scene.session_id} onChange={set("session_id")} options={sessionOptions} placeholder="— Backlog —" />
        </label>
        <label className="field spanAll">
          <span>Description</span>
          <textarea value={scene.description} onChange={setInput("description")} rows={2} placeholder="Brief prose description shown on the scene card" />
        </label>
        <CreatableMultiTagSelect label="Cast" value={scene.cast} onChange={set("cast")}
          onCreateNew={handleCreateNewCast} placeholder="Search or add cast…" suggestions={castSuggestions} />
        <CreatableMultiTagSelect label="Location" value={scene.location} onChange={set("location")}
          onCreateNew={handleCreateNewLocation} placeholder="Search or add location…" suggestions={locationSuggestions} />
        <CreatableMultiTagSelect label="Clock / Thread" value={scene.clock} onChange={set("clock")}
          onCreateNew={handleCreateNewClock} placeholder="Search or add clock…" suggestions={clockSuggestions} />
      </div>

      {/* Scene Shape */}
      <CollapsibleSection title="Scene Shape" defaultOpen={false}>
        <div className="formGrid">
          <div className="field">
            <span>Cuttable</span>
            <button type="button" className={scene.cuttable ? "active" : ""}
              onClick={() => setScene((p) => ({ ...p, cuttable: !p.cuttable }))}>
              {scene.cuttable ? "Yes — scene can be cut" : "No — scene is fixed"}
            </button>
          </div>
          <label className="field spanAll"><span>Purpose</span>
            <input value={scene.purpose} onChange={setInput("purpose")} placeholder="What does this scene accomplish?" /></label>
          <label className="field spanAll"><span>PC Pressure</span>
            <input value={scene.pc_pressure} onChange={setInput("pc_pressure")} placeholder="Which PC lane does this press on?" /></label>
          <label className="field spanAll"><span>Entry Pressure</span>
            <input value={scene.entry_pressure} onChange={setInput("entry_pressure")} placeholder="What are the PCs facing at the start?" /></label>
          <label className="field spanAll"><span>Exit Condition</span>
            <input value={scene.exit_condition} onChange={setInput("exit_condition")} placeholder="What ends the scene?" /></label>
        </div>
      </CollapsibleSection>

      {/* Material Pins */}
      <CollapsibleSection title="Material Pins" defaultOpen={false}>
        <div className="scene-pins-bar">
          <button onClick={() => setPinsModalOpen(true)}><Search size={14} /> Browse vault</button>
          <span className="scene-pins-count">{pinnedMaterial.length > 0 ? `${pinnedMaterial.length} pinned` : "No pins yet"}</span>
        </div>
        {pinnedMaterial.length > 0 && (
          <div className="scene-pins-list">
            {pinnedMaterial.map((item) => (
              <span key={item.path} className="tag">
                {item.title}
                <button type="button" className="tag-remove" onClick={() => unpinItem(item.path)}>×</button>
              </span>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* Clue Structure */}
      <CollapsibleSection title="Clue Structure" defaultOpen={false}>
        <div className="formGrid">
          <label className="field spanAll"><span>Core information</span>
            <textarea value={scene.core_clue} onChange={setInput("core_clue")} placeholder="What must the PCs learn?" rows={2} /></label>
          <label className="field spanAll"><span>Superior information</span>
            <textarea value={scene.superior_clue} onChange={setInput("superior_clue")} placeholder="Learned if they succeed or roll well" rows={2} /></label>
          <label className="field spanAll"><span>Optional information</span>
            <textarea value={scene.optional_clue} onChange={setInput("optional_clue")} placeholder="Adds color or leverage" rows={2} /></label>
          <label className="field spanAll"><span>False lead risk</span>
            <textarea value={scene.false_lead} onChange={setInput("false_lead")} placeholder="Could this mislead them?" rows={2} /></label>
        </div>
      </CollapsibleSection>

      {/* Sensory Prep */}
      <CollapsibleSection title="Sensory Prep" defaultOpen={false}>
        <div className="formGrid">
          <label className="field spanAll"><span>Opening image</span>
            <input value={scene.opening_image} onChange={setInput("opening_image")} placeholder="First visual impression" /></label>
          <label className="field spanAll"><span>Sensory words</span>
            <input value={scene.sensory_words} onChange={setInput("sensory_words")} placeholder="wet stone, rust, incense ash…" /></label>
          <label className="field spanAll"><span>Interactable objects</span>
            <input value={scene.interactable_objects} onChange={setInput("interactable_objects")} placeholder="duty board, cracked mask…" /></label>
        </div>
      </CollapsibleSection>

      {/* Contingencies */}
      <CollapsibleSection title="Contingencies" defaultOpen={false}>
        <div className="formGrid">
          <label className="field"><span>Rules likely</span>
            <input value={scene.rules_likely} onChange={setInput("rules_likely")} placeholder="stealth, grapples, chase…" /></label>
          <label className="field"><span>Foundry needs</span>
            <input value={scene.foundry_needs} onChange={setInput("foundry_needs")} placeholder="map, tokens, handout" /></label>
          <label className="field spanAll"><span>Replacement route</span>
            <input value={scene.replacement_route} onChange={setInput("replacement_route")} placeholder="If players bypass the prep?" /></label>
          <label className="field spanAll"><span>If PCs succeed</span>
            <textarea value={scene.if_succeed} onChange={setInput("if_succeed")} rows={1} /></label>
          <label className="field spanAll"><span>If PCs fail</span>
            <textarea value={scene.if_fail} onChange={setInput("if_fail")} rows={1} /></label>
          <label className="field spanAll"><span>If PCs ignore it</span>
            <textarea value={scene.if_ignore} onChange={setInput("if_ignore")} rows={1} /></label>
          <label className="field spanAll"><span>If time is short</span>
            <textarea value={scene.if_short} onChange={setInput("if_short")} rows={1} /></label>
        </div>
      </CollapsibleSection>

      {/* Notes */}
      <CollapsibleSection title="Notes" defaultOpen={false}>
        <div className="formGrid">
          <label className="field spanAll"><span>Notes</span>
            <textarea value={scene.notes} onChange={setInput("notes")} rows={2} /></label>
        </div>
      </CollapsibleSection>

      {/* Draft output */}
      {sceneDraft ? (
        <div className="draftGrid" style={{ marginTop: "var(--space-5)" }}>
          <label className="field">
            <span>Editable draft — {sceneDraft.path}</span>
            <textarea value={sceneText} onChange={(e) => setSceneText(e.target.value)} />
          </label>
          <label className="field"><span>Preview</span><pre>{sceneText}</pre></label>
          <div className="saveFlow diffBox">
            <label className="field" style={{ marginBottom: "var(--space-3)" }}>
              <span>Canonical target path</span>
              <input value={sceneTarget} onChange={(e) => setSceneTarget(e.target.value)} />
            </label>
            <div className="saveActions">
              <button onClick={previewDraft}><Eye size={16} /> Preview Save</button>
              <button onClick={saveDraftToVault}><Save size={16} /> Confirm Save</button>
            </div>
          </div>
          {sceneSavePreview && (
            <label className="field diffBox"><span>Canonical diff</span><pre>{sceneSavePreview.diff}</pre></label>
          )}
        </div>
      ) : (
        <div className="draftPlaceholder" style={{ marginTop: "var(--space-5)" }}>
          Draft appears here after Create Draft
        </div>
      )}

      {/* Action bar */}
      <div className="saveFlow" style={{ marginTop: "var(--space-4)" }}>
        <div className="saveActions">
          {scene.id && (
            <button onClick={handleDelete} style={{ color: "#c97070" }}>
              <Trash size={16} /> Delete
            </button>
          )}
          <button onClick={createDraft}><Plus size={16} /> Create Draft</button>
          <button onClick={handleSave} className="active"><Save size={16} /> Save Scene</button>
        </div>
      </div>

      <PinsModal
        open={pinsModalOpen}
        onClose={() => setPinsModalOpen(false)}
        runAction={runAction}
        onStatusChange={onStatusChange}
        onPin={pinItem}
        pinnedPaths={pinnedPaths}
      />
    </>
  );
}
