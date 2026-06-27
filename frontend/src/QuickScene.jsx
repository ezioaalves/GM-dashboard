import React, { useState } from "react";
import { ChevronDown, Plus, Save, X, Search, Eye } from "lucide-react";

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
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: "rgba(0,0,0,0.7)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000,
    }}>
      <div style={{
        backgroundColor: "var(--color-surface)",
        borderRadius: 8,
        border: "1px solid var(--color-border-strong)",
        width: "90%",
        maxWidth: 1200,
        height: "80vh",
        display: "flex",
        flexDirection: "column",
        padding: 20,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ margin: 0 }}>Select Material to Pin</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#ccc" }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search NPCs, locations, threads, clues..."
            onKeyDown={(e) => e.key === "Enter" && pinSearch()}
            style={{
              flex: 1,
              padding: "8px 12px",
              backgroundColor: "var(--color-card)",
              border: "1px solid var(--color-border-strong)",
              color: "var(--color-text-secondary)",
              borderRadius: 4,
            }}
          />
          <button onClick={pinSearch} style={{ padding: "8px 16px", backgroundColor: "var(--color-accent)", border: "none", color: "white", cursor: "pointer", borderRadius: 4 }}>
            <Search size={16} /> Search
          </button>
        </div>

        <div style={{ flex: 1, display: "flex", gap: 16, overflow: "hidden" }}>
          {/* Results list */}
          <div style={{
            flex: "0 0 35%",
            overflowY: "auto",
            borderRight: "1px solid #555",
            paddingRight: 12,
          }}>
            {results.length === 0 && query ? (
              <p style={{ color: "var(--color-text-muted)", fontSize: 12 }}>No results found.</p>
            ) : results.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)", fontSize: 12 }}>Type to search...</p>
            ) : (
              results.map((row) => {
                const isPinned = pinnedPaths.includes(row.path);
                return (
                  <div
                    key={row.path}
                    style={{
                      padding: 10,
                      marginBottom: 8,
                      backgroundColor: selectedPath === row.path ? "rgba(74,157,131,0.3)" : "rgba(100,100,100,0.1)",
                      border: `1px solid ${selectedPath === row.path ? "var(--color-accent)" : "#555"}`,
                      borderRadius: 4,
                      cursor: "pointer",
                    }}
                  >
                    <div onClick={() => viewContent(row.path)} style={{ marginBottom: 8 }}>
                      <h4 style={{ margin: "0 0 4px 0", fontSize: 13 }}>{row.title}</h4>
                      <p style={{ margin: "0 0 4px 0", fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.3 }}>{row.snippet}</p>
                      <code style={{ fontSize: 9, color: "var(--color-text-muted)" }}>{row.path}</code>
                    </div>
                    <button
                      onClick={() => handlePin(row)}
                      disabled={isPinned}
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        fontSize: 12,
                        backgroundColor: isPinned ? "#666" : "var(--color-accent)",
                        border: "none",
                        color: "white",
                        cursor: isPinned ? "default" : "pointer",
                        borderRadius: 3,
                      }}
                    >
                      {isPinned ? "Already pinned" : "Pin"}
                    </button>
                  </div>
                );
              })
            )}
          </div>

          {/* Content preview */}
          <div style={{
            flex: "0 0 65%",
            overflowY: "auto",
            paddingLeft: 12,
          }}>
            {selectedPath ? (
              <div>
                <h4 style={{ margin: "0 0 12px 0", wordBreak: "break-word" }}>{selectedPath}</h4>
                <pre style={{
                  backgroundColor: "#2a2a2a",
                  border: "1px solid var(--color-border-strong)",
                  borderRadius: 4,
                  padding: 12,
                  fontSize: 12,
                  lineHeight: 1.4,
                  maxHeight: "100%",
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {selectedContent}
                </pre>
              </div>
            ) : (
              <p style={{ color: "var(--color-text-muted)", fontSize: 12 }}>Select a result to preview</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function AutocompleteField({ label, value, onChange, onCreateNew, placeholder, suggestions }) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");

  const filtered = suggestions.filter((s) => s.toLowerCase().includes(inputValue.toLowerCase()));
  const hasMatch = filtered.some((s) => s.toLowerCase() === inputValue.toLowerCase());

  function handleSelect(item) {
    onChange([...value, item]);
    setInputValue("");
    setOpen(false);
  }

  function handleCreateNew() {
    if (inputValue.trim()) {
      onCreateNew(inputValue);
      setInputValue("");
      setOpen(false);
    }
  }

  return (
    <div style={{ position: "relative" }}>
      <label style={{ display: "block", marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{label}</span>
      </label>

      {/* Display selected items as tags */}
      {value.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
          {value.map((item) => (
            <div
              key={item}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "4px 8px",
                backgroundColor: "rgba(74,157,131,0.2)",
                border: "1px solid var(--color-accent)",
                fontSize: 12,
                borderRadius: 3,
              }}
            >
              {item}
              <button
                onClick={() => onChange(value.filter((v) => v !== item))}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--color-text-muted)",
                  padding: 0,
                }}
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input field */}
      <div style={{ position: "relative" }}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          style={{
            width: "100%",
            padding: "6px 8px",
            backgroundColor: "#2a2a2a",
            border: "1px solid var(--color-border-strong)",
            color: "#ccc",
            borderRadius: 4,
            fontSize: 12,
          }}
        />

        {/* Dropdown */}
        {open && inputValue && (
          <div style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            backgroundColor: "#2a2a2a",
            border: "1px solid var(--color-border-strong)",
            borderTop: "none",
            borderRadius: "0 0 4px 4px",
            maxHeight: 200,
            overflowY: "auto",
            zIndex: 100,
          }}>
            {filtered.map((item) => (
              <div
                key={item}
                onClick={() => handleSelect(item)}
                style={{
                  padding: "8px 12px",
                  cursor: "pointer",
                  borderBottom: "1px solid var(--color-border)",
                  fontSize: 12,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(74,157,131,0.2)")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
              >
                {item}
              </div>
            ))}
            {!hasMatch && inputValue && (
              <div
                onClick={handleCreateNew}
                style={{
                  padding: "8px 12px",
                  cursor: "pointer",
                  backgroundColor: "rgba(74,157,131,0.1)",
                  color: "var(--color-accent)",
                  fontSize: 12,
                  fontWeight: 600,
                  borderTop: "1px solid #555",
                }}
              >
                + Create "{inputValue}"
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)} style={{ marginBottom: 0 }}>
      <summary
        style={{
          cursor: "pointer",
          padding: "12px 0",
          fontSize: 14,
          fontWeight: 600,
          color: "#ccc",
          display: "flex",
          alignItems: "center",
          gap: 8,
          userSelect: "none",
          borderBottom: "1px solid var(--color-border)",
          marginBottom: open ? 16 : 0,
        }}
      >
        <ChevronDown size={16} style={{ transform: open ? "rotate(0deg)" : "rotate(-90deg)", transition: "transform 0.2s" }} />
        {title}
      </summary>
      <div style={{ paddingBottom: 16 }}>{children}</div>
    </details>
  );
}

export default function QuickScene({ onStatusChange, onErrorChange, runAction }) {
  const [scene, setScene] = useState({
    title: "",
    type: "",
    cuttable: false,
    purpose: "",
    pc_pressure: "",
    entry_pressure: "",
    exit_condition: "",
    cast: [],
    location: [],
    clock: [],
    core_clue: "",
    superior_clue: "",
    optional_clue: "",
    false_lead: "",
    opening_image: "",
    sensory_words: "",
    interactable_objects: "",
    rules_likely: "",
    foundry_needs: "",
    replacement_route: "",
    if_succeed: "",
    if_fail: "",
    if_ignore: "",
    if_short: "",
    notes: "",
  });

  const [pinnedMaterial, setPinnedMaterial] = useState([]);
  const [pinsModalOpen, setPinsModalOpen] = useState(false);
  const [sceneDraft, setSceneDraft] = useState(null);
  const [sceneText, setSceneText] = useState("");
  const [sceneTarget, setSceneTarget] = useState("");
  const [sceneSavePreview, setSceneSavePreview] = useState(null);

  // Autocomplete suggestions — fetched from vault initially
  const [castSuggestions, setCastSuggestions] = useState(["Dan", "Ikazuchi", "Suigin", "Kubo"]);
  const [locationSuggestions, setLocationSuggestions] = useState(["Iron Keep", "Kanigakure", "Training grounds", "Forest"]);
  const [clockSuggestions, setClockSuggestions] = useState(["Shadowlands escalation", "Exam countdown", "Clan pressure", "Mystery investigation"]);

  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  function handleCreateNewCast(name) {
    setCastSuggestions([...castSuggestions, name]);
    setScene({ ...scene, cast: [...scene.cast, name] });
    onStatusChange(`Cast stub created: ${name}`);
    // Future: write to DB
  }

  function handleCreateNewLocation(name) {
    setLocationSuggestions([...locationSuggestions, name]);
    setScene({ ...scene, location: [...scene.location, name] });
    onStatusChange(`Location stub created: ${name}`);
    // Future: write to DB
  }

  function handleCreateNewClock(name) {
    setClockSuggestions([...clockSuggestions, name]);
    setScene({ ...scene, clock: [...scene.clock, name] });
    onStatusChange(`Clock stub created: ${name}`);
    // Future: write to DB
  }

  function pinItem(result) {
    setPinnedMaterial([...pinnedMaterial, result]);
  }

  function unpinItem(path) {
    setPinnedMaterial(pinnedMaterial.filter((item) => item.path !== path));
  }

  async function quickScene() {
    await runAction("Creating scene draft...", async () => {
      const castStr = scene.cast.join(", ");
      const locationStr = scene.location.join(", ");
      const clockStr = scene.clock.join(", ");

      const json = await postJson("/api/capture/scene", {
        title: scene.title || "Untitled Scene",
        type: scene.type,
        cuttable: scene.cuttable,
        purpose: scene.purpose,
        pc_pressure: scene.pc_pressure,
        entry_pressure: scene.entry_pressure,
        exit_condition: scene.exit_condition,
        cast: castStr,
        location: locationStr,
        clock: clockStr,
        core_clue: scene.core_clue,
        superior_clue: scene.superior_clue,
        optional_clue: scene.optional_clue,
        false_lead: scene.false_lead,
        opening_image: scene.opening_image,
        sensory_words: scene.sensory_words,
        interactable_objects: scene.interactable_objects,
        rules_likely: scene.rules_likely,
        foundry_needs: scene.foundry_needs,
        replacement_route: scene.replacement_route,
        if_succeed: scene.if_succeed,
        if_fail: scene.if_fail,
        if_ignore: scene.if_ignore,
        if_short: scene.if_short,
        notes: scene.notes,
        pinned_material: pinnedMaterial,
      });
      setSceneDraft(json);
      setSceneText(json.markdown);
      setSceneTarget(json.default_target_path);
      setSceneSavePreview(null);
      onStatusChange(`Scene draft written to ${json.path}`);
    });
  }

  async function previewDraft(draft, targetPath, markdown, setPreview) {
    if (!draft) return;
    await runAction(`Preparing diff for ${targetPath}...`, async () => {
      const json = await postJson(`/api/drafts/${draft.id}/preview`, { target_path: targetPath, markdown });
      setPreview(json);
      onStatusChange(`Preview ready for ${json.path}.`);
    });
  }

  async function saveDraft(draft, targetPath, markdown, setPreview) {
    if (!draft) return;
    await runAction(`Saving ${targetPath}...`, async () => {
      const json = await postJson(`/api/drafts/${draft.id}/save`, { target_path: targetPath, markdown, confirm: true });
      setPreview(json);
      onStatusChange(`Canonical Markdown saved to ${json.path}.`);
    });
  }

  const pinnedPaths = pinnedMaterial.map((m) => m.path);

  return (
    <>
      <div className="toolPanel">
        <div className="panelHeader">
          <div>
            <h2>Quick Scene</h2>
            <p>Compact card for a runnable beat.</p>
          </div>
        </div>

        {/* Title — top-level, always visible */}
        <div className="formGrid" style={{ marginBottom: 20 }}>
          <label className="field spanAll">
            <span>Title</span>
            <input
              value={scene.title}
              onChange={(e) => setScene({ ...scene, title: e.target.value })}
              placeholder="Scene name or hook"
              style={{ width: "100%", padding: "6px 8px" }}
            />
          </label>
        </div>

        {/* Section 1: Scene Shape */}
        <CollapsibleSection title="Scene Shape" defaultOpen={true}>
          <div className="formGrid">
            <label className="field">
              <span>Type</span>
              <select
                value={scene.type}
                onChange={(e) => setScene({ ...scene, type: e.target.value })}
                style={{ padding: "6px 8px", fontSize: 12 }}
              >
                <option value="">— Select —</option>
                <option value="Hard">Hard / Core</option>
                <option value="Soft">Soft / Supplemental</option>
                <option value="Cut">Cut</option>
                <option value="Added">Added</option>
                <option value="Replacement">Replacement</option>
                <option value="Spotlight">Spotlight</option>
                <option value="Bridge">Bridge</option>
              </select>
            </label>
            <label className="field">
              <span>Cuttable</span>
              <input type="checkbox" checked={scene.cuttable} onChange={(e) => setScene({ ...scene, cuttable: e.target.checked })} />
            </label>
            <label className="field spanAll">
              <span>Purpose</span>
              <input
                value={scene.purpose}
                onChange={(e) => setScene({ ...scene, purpose: e.target.value })}
                placeholder="What does this accomplish?"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>PC Pressure</span>
              <input
                value={scene.pc_pressure}
                onChange={(e) => setScene({ ...scene, pc_pressure: e.target.value })}
                placeholder="Which PC lane?"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>Entry Pressure</span>
              <input
                value={scene.entry_pressure}
                onChange={(e) => setScene({ ...scene, entry_pressure: e.target.value })}
                placeholder="What PCs face at the start"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>Exit Condition</span>
              <input
                value={scene.exit_condition}
                onChange={(e) => setScene({ ...scene, exit_condition: e.target.value })}
                placeholder="What ends the scene?"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
          </div>
        </CollapsibleSection>

        {/* Section 2: Cast & Location */}
        <CollapsibleSection title="Cast & Location" defaultOpen={false}>
          <div className="formGrid">
            <AutocompleteField
              label="Cast"
              value={scene.cast}
              onChange={(val) => setScene({ ...scene, cast: val })}
              onCreateNew={handleCreateNewCast}
              placeholder="Search or create cast..."
              suggestions={castSuggestions}
            />
            <AutocompleteField
              label="Location"
              value={scene.location}
              onChange={(val) => setScene({ ...scene, location: val })}
              onCreateNew={handleCreateNewLocation}
              placeholder="Search or create location..."
              suggestions={locationSuggestions}
            />
            <AutocompleteField
              label="Clock/thread"
              value={scene.clock}
              onChange={(val) => setScene({ ...scene, clock: val })}
              onCreateNew={handleCreateNewClock}
              placeholder="Search or create clock..."
              suggestions={clockSuggestions}
            />
          </div>
        </CollapsibleSection>

        {/* Section 3: Material Pins */}
        <CollapsibleSection title="Material Pins" defaultOpen={false}>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <button
              onClick={() => setPinsModalOpen(true)}
              style={{
                padding: "8px 16px",
                backgroundColor: "var(--color-accent)",
                border: "none",
                color: "white",
                cursor: "pointer",
                borderRadius: 4,
                fontSize: 12,
              }}
            >
              Edit Pins
            </button>
            <span style={{ fontSize: 12, color: "var(--color-text-muted)", alignSelf: "center" }}>
              {pinnedMaterial.length} pinned
            </span>
          </div>

          {pinnedMaterial.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {pinnedMaterial.map((item) => (
                <div
                  key={item.path}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 10px",
                    backgroundColor: "rgba(74,157,131,0.2)",
                    border: "1px solid var(--color-accent)",
                    fontSize: 12,
                    borderRadius: 3,
                  }}
                >
                  <span>{item.title}</span>
                  <button
                    onClick={() => unpinItem(item.path)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0,
                      color: "var(--color-text-muted)",
                    }}
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>

        {/* Section 4: Clue Structure */}
        <CollapsibleSection title="Clue Structure" defaultOpen={false}>
          <div className="formGrid">
            <label className="field spanAll">
              <span>Core information</span>
              <textarea
                value={scene.core_clue}
                onChange={(e) => setScene({ ...scene, core_clue: e.target.value })}
                placeholder="What must PCs learn?"
                rows="2"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>Superior information</span>
              <textarea
                value={scene.superior_clue}
                onChange={(e) => setScene({ ...scene, superior_clue: e.target.value })}
                placeholder="Learned if they succeed/roll well"
                rows="2"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>Optional information</span>
              <textarea
                value={scene.optional_clue}
                onChange={(e) => setScene({ ...scene, optional_clue: e.target.value })}
                placeholder="Adds color or leverage"
                rows="2"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>False lead risk</span>
              <textarea
                value={scene.false_lead}
                onChange={(e) => setScene({ ...scene, false_lead: e.target.value })}
                placeholder="Could mislead them?"
                rows="2"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
          </div>
        </CollapsibleSection>

        {/* Section 5: Sensory Prep */}
        <CollapsibleSection title="Sensory Prep" defaultOpen={false}>
          <div className="formGrid">
            <label className="field spanAll">
              <span>Opening image</span>
              <input
                value={scene.opening_image}
                onChange={(e) => setScene({ ...scene, opening_image: e.target.value })}
                placeholder="First visual impression"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>Sensory words</span>
              <input
                value={scene.sensory_words}
                onChange={(e) => setScene({ ...scene, sensory_words: e.target.value })}
                placeholder="wet stone, rust, incense ash…"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>Interactable objects</span>
              <input
                value={scene.interactable_objects}
                onChange={(e) => setScene({ ...scene, interactable_objects: e.target.value })}
                placeholder="duty board, cracked mask…"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
          </div>
        </CollapsibleSection>

        {/* Section 6: Contingencies */}
        <CollapsibleSection title="Contingencies" defaultOpen={false}>
          <div className="formGrid">
            <label className="field">
              <span>Rules likely</span>
              <input
                value={scene.rules_likely}
                onChange={(e) => setScene({ ...scene, rules_likely: e.target.value })}
                placeholder="stealth, grapples, chase…"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field">
              <span>Foundry needs</span>
              <input
                value={scene.foundry_needs}
                onChange={(e) => setScene({ ...scene, foundry_needs: e.target.value })}
                placeholder="map, tokens, handout"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>Replacement route</span>
              <input
                value={scene.replacement_route}
                onChange={(e) => setScene({ ...scene, replacement_route: e.target.value })}
                placeholder="If players bypass the prep?"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>If PCs succeed</span>
              <textarea
                value={scene.if_succeed}
                onChange={(e) => setScene({ ...scene, if_succeed: e.target.value })}
                rows="1"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>If PCs fail</span>
              <textarea
                value={scene.if_fail}
                onChange={(e) => setScene({ ...scene, if_fail: e.target.value })}
                rows="1"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>If PCs ignore it</span>
              <textarea
                value={scene.if_ignore}
                onChange={(e) => setScene({ ...scene, if_ignore: e.target.value })}
                rows="1"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
            <label className="field spanAll">
              <span>If time is short</span>
              <textarea
                value={scene.if_short}
                onChange={(e) => setScene({ ...scene, if_short: e.target.value })}
                rows="1"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
          </div>
        </CollapsibleSection>

        {/* Section 7: Notes */}
        <CollapsibleSection title="Notes" defaultOpen={false}>
          <div className="formGrid">
            <label className="field spanAll">
              <span>Notes</span>
              <textarea
                value={scene.notes}
                onChange={(e) => setScene({ ...scene, notes: e.target.value })}
                rows="2"
                style={{ width: "100%", padding: "6px 8px", fontSize: 12 }}
              />
            </label>
          </div>
        </CollapsibleSection>

        {/* Create Scene Draft — at the bottom */}
        <div style={{ marginTop: 24, marginBottom: 20 }}>
          <button
            onClick={quickScene}
            style={{
              width: "100%",
              padding: "10px 16px",
              backgroundColor: "var(--color-accent)",
              border: "none",
              color: "white",
              cursor: "pointer",
              borderRadius: 4,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <Plus size={16} style={{ marginRight: 8, display: "inline" }} /> Create Scene Draft
          </button>
        </div>

        {/* Draft preview & save */}
        {sceneDraft && (
          <div className="draftGrid">
            <label className="field">
              <span>Editable Scene Draft - {sceneDraft.path}</span>
              <textarea value={sceneText} onChange={(e) => setSceneText(e.target.value)} style={{ fontSize: 12 }} />
            </label>
            <label className="field">
              <span>Preview</span>
              <pre style={{ fontSize: 11, lineHeight: 1.3 }}>{sceneText}</pre>
            </label>
            <div className="saveFlow diffBox">
              <label className="field" style={{ marginBottom: 12 }}>
                <span>Canonical target path</span>
                <input value={sceneTarget} onChange={(e) => setSceneTarget(e.target.value)} style={{ fontSize: 12 }} />
              </label>
              <div className="saveActions">
                <button onClick={() => previewDraft(sceneDraft, sceneTarget, sceneText, setSceneSavePreview)}>
                  <Eye size={16} /> Preview Save
                </button>
                <button onClick={() => saveDraft(sceneDraft, sceneTarget, sceneText, setSceneSavePreview)}>
                  <Save size={16} /> Confirm Save
                </button>
              </div>
            </div>
            {sceneSavePreview && (
              <label className="field diffBox">
                <span>Canonical Diff</span>
                <pre style={{ fontSize: 11 }}>{sceneSavePreview.diff}</pre>
              </label>
            )}
          </div>
        )}
        {!sceneDraft && (
          <div className="draftPlaceholder" style={{ marginTop: "1rem", textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
            Draft appears here after Create Scene Draft
          </div>
        )}
      </div>

      {/* Pins Modal */}
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
