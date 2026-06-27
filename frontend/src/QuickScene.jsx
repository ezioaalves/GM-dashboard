import React, { useState } from "react";
import { Eye, Plus, Save, X, Search } from "lucide-react";

export default function QuickScene({ onStatusChange, onErrorChange, runAction }) {
  const [scene, setScene] = useState({
    title: "",
    type: "",
    cuttable: false,
    purpose: "",
    pc_pressure: "",
    entry_pressure: "",
    exit_condition: "",
    cast: "",
    location: "",
    clock: "",
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
  const [pinQuery, setPinQuery] = useState("");
  const [pinResults, setPinResults] = useState([]);
  const [sceneDraft, setSceneDraft] = useState(null);
  const [sceneText, setSceneText] = useState("");
  const [sceneTarget, setSceneTarget] = useState("");
  const [sceneSavePreview, setSceneSavePreview] = useState(null);

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

  async function pinSearch() {
    if (!pinQuery.trim()) return;
    await runAction("Searching vault...", async () => {
      const res = await fetch(`/api/search?q=${encodeURIComponent(pinQuery)}&limit=12`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setPinResults(json);
      onStatusChange(`Found ${json.length} result${json.length === 1 ? "" : "s"} for "${pinQuery}".`);
    });
  }

  function pinItem(result) {
    setPinnedMaterial([...pinnedMaterial, result]);
    setPinResults(pinResults.filter((r) => r.path !== result.path));
  }

  function unpinItem(path) {
    setPinnedMaterial(pinnedMaterial.filter((item) => item.path !== path));
  }

  async function quickScene() {
    await runAction("Creating scene draft...", async () => {
      const json = await postJson("/api/capture/scene", {
        title: scene.title || "Untitled Scene",
        type: scene.type,
        cuttable: scene.cuttable,
        purpose: scene.purpose,
        pc_pressure: scene.pc_pressure,
        entry_pressure: scene.entry_pressure,
        exit_condition: scene.exit_condition,
        cast: splitList(scene.cast),
        location: scene.location,
        clock: scene.clock,
        core_clue: scene.core_clue,
        superior_clue: scene.superior_clue,
        optional_clue: scene.optional_clue,
        false_lead: scene.false_lead,
        opening_image: scene.opening_image,
        sensory_words: scene.sensory_words,
        interactable_objects: scene.interactable_objects,
        rules_likely: scene.rules_likely,
        foundry_needs: splitList(scene.foundry_needs),
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

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>Quick Scene</h2>
          <p>Compact card for a runnable beat: purpose, cast, clue, clock, and Foundry needs.</p>
        </div>
        <button onClick={quickScene}><Plus size={16} /> Create Scene Draft</button>
      </div>

      {/* Title — top-level, always visible */}
      <div className="formGrid">
        <label className="field spanAll">
          <span>Title</span>
          <input
            value={scene.title}
            onChange={(e) => setScene({ ...scene, title: e.target.value })}
            placeholder="Scene name or hook"
          />
        </label>
      </div>

      {/* Section 1: Scene Shape */}
      <div style={{ marginTop: "1.5rem" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#ccc" }}>Scene Shape</h3>
        <div className="formGrid">
          <label className="field">
            <span>Type</span>
            <select value={scene.type} onChange={(e) => setScene({ ...scene, type: e.target.value })}>
              <option value="">— Select type —</option>
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
            <input
              type="checkbox"
              checked={scene.cuttable}
              onChange={(e) => setScene({ ...scene, cuttable: e.target.checked })}
              style={{ width: 20, height: 20 }}
            />
          </label>
          <label className="field spanAll">
            <span>Purpose</span>
            <input
              value={scene.purpose}
              onChange={(e) => setScene({ ...scene, purpose: e.target.value })}
              placeholder="What does this scene accomplish?"
            />
          </label>
          <label className="field spanAll">
            <span>PC Pressure</span>
            <input
              value={scene.pc_pressure}
              onChange={(e) => setScene({ ...scene, pc_pressure: e.target.value })}
              placeholder="Which PC lane does this pressure?"
            />
          </label>
          <label className="field spanAll">
            <span>Entry Pressure</span>
            <input
              value={scene.entry_pressure}
              onChange={(e) => setScene({ ...scene, entry_pressure: e.target.value })}
              placeholder="What PCs see/face when the scene opens"
            />
          </label>
          <label className="field spanAll">
            <span>Exit Condition</span>
            <input
              value={scene.exit_condition}
              onChange={(e) => setScene({ ...scene, exit_condition: e.target.value })}
              placeholder="What ends the scene?"
            />
          </label>
        </div>
      </div>

      {/* Section 2: Cast & Location */}
      <div style={{ marginTop: "1.5rem" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#ccc" }}>Cast & Location</h3>
        <div className="formGrid">
          <label className="field">
            <span>Cast</span>
            <input
              value={scene.cast}
              onChange={(e) => setScene({ ...scene, cast: e.target.value })}
              placeholder="Dan, Ikazuchi, Suigin"
            />
          </label>
          <label className="field">
            <span>Location</span>
            <input
              value={scene.location}
              onChange={(e) => setScene({ ...scene, location: e.target.value })}
              placeholder="Where does it happen?"
            />
          </label>
          <label className="field spanAll">
            <span>Clock/thread</span>
            <input
              value={scene.clock}
              onChange={(e) => setScene({ ...scene, clock: e.target.value })}
              placeholder="Which clock or thread advances?"
            />
          </label>
        </div>
      </div>

      {/* Section 3: Material Pins */}
      <div style={{ marginTop: "1.5rem" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#ccc" }}>Material Pins</h3>
        <div className="formGrid" style={{ marginBottom: 12 }}>
          <label className="field" style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <span style={{ flex: 1 }}>Search vault</span>
            <input
              value={pinQuery}
              onChange={(e) => setPinQuery(e.target.value)}
              placeholder="Search for NPCs, locations, threads..."
              onKeyDown={(e) => e.key === "Enter" && pinSearch()}
            />
            <button onClick={pinSearch} style={{ whiteSpace: "nowrap" }}>
              <Search size={16} /> Search
            </button>
          </label>
        </div>

        {/* Pin search results */}
        {pinResults.length > 0 && (
          <div style={{ marginBottom: 12, borderTop: "1px solid #555", paddingTop: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#aaa", marginBottom: 8 }}>Results</div>
            {pinResults.map((row) => (
              <article
                className="card"
                key={row.path}
                style={{
                  marginBottom: 8,
                  padding: 8,
                  backgroundColor: "rgba(100,150,200,0.05)",
                  border: "1px solid #555",
                }}
              >
                <h4 style={{ margin: "0 0 4px 0" }}>{row.title}</h4>
                <p style={{ margin: "0 0 4px 0", fontSize: 12, color: "#aaa" }}>{row.snippet}</p>
                <code style={{ fontSize: 10, color: "#888" }}>{row.path}</code>
                <button
                  onClick={() => pinItem(row)}
                  style={{
                    marginTop: 4,
                    padding: "4px 8px",
                    fontSize: 12,
                    cursor: "pointer",
                    backgroundColor: "#4a9d83",
                    border: "none",
                    color: "white",
                  }}
                >
                  Pin
                </button>
              </article>
            ))}
          </div>
        )}

        {/* Pinned items */}
        {pinnedMaterial.length > 0 && (
          <div style={{ borderTop: "1px solid #555", paddingTop: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#aaa", marginBottom: 8 }}>
              Pinned {pinnedMaterial.length > 1 ? "items" : "item"}
            </div>
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
                    border: "1px solid #4a9d83",
                    fontSize: 12,
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
                      color: "#aaa",
                    }}
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Section 4: Clue Structure */}
      <div style={{ marginTop: "1.5rem" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#ccc" }}>Clue Structure</h3>
        <div className="formGrid">
          <label className="field spanAll">
            <span>Core information</span>
            <textarea
              value={scene.core_clue}
              onChange={(e) => setScene({ ...scene, core_clue: e.target.value })}
              placeholder="What must PCs learn or discover?"
              rows="2"
            />
          </label>
          <label className="field spanAll">
            <span>Superior information</span>
            <textarea
              value={scene.superior_clue}
              onChange={(e) => setScene({ ...scene, superior_clue: e.target.value })}
              placeholder="What do they learn if they succeed/roll well?"
              rows="2"
            />
          </label>
          <label className="field spanAll">
            <span>Optional information</span>
            <textarea
              value={scene.optional_clue}
              onChange={(e) => setScene({ ...scene, optional_clue: e.target.value })}
              placeholder="What adds color or leverage?"
              rows="2"
            />
          </label>
          <label className="field spanAll">
            <span>False lead risk</span>
            <textarea
              value={scene.false_lead}
              onChange={(e) => setScene({ ...scene, false_lead: e.target.value })}
              placeholder="What could mislead them?"
              rows="2"
            />
          </label>
        </div>
      </div>

      {/* Section 5: Sensory Prep */}
      <div style={{ marginTop: "1.5rem" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#ccc" }}>Sensory Prep</h3>
        <div className="formGrid">
          <label className="field spanAll">
            <span>Opening image</span>
            <input
              value={scene.opening_image}
              onChange={(e) => setScene({ ...scene, opening_image: e.target.value })}
              placeholder="What do PCs see first?"
            />
          </label>
          <label className="field spanAll">
            <span>Sensory words</span>
            <input
              value={scene.sensory_words}
              onChange={(e) => setScene({ ...scene, sensory_words: e.target.value })}
              placeholder="wet stone, rust, incense ash, drilled silence, distant horns"
            />
          </label>
          <label className="field spanAll">
            <span>Interactable objects</span>
            <input
              value={scene.interactable_objects}
              onChange={(e) => setScene({ ...scene, interactable_objects: e.target.value })}
              placeholder="duty board, cracked mask, sealed ration crate, blood-marked report"
            />
          </label>
        </div>
      </div>

      {/* Section 6: Contingencies */}
      <div style={{ marginTop: "1.5rem" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#ccc" }}>Contingencies</h3>
        <div className="formGrid">
          <label className="field">
            <span>Rules likely</span>
            <input
              value={scene.rules_likely}
              onChange={(e) => setScene({ ...scene, rules_likely: e.target.value })}
              placeholder="stealth, grapples, chase, etc."
            />
          </label>
          <label className="field">
            <span>Foundry needs</span>
            <input
              value={scene.foundry_needs}
              onChange={(e) => setScene({ ...scene, foundry_needs: e.target.value })}
              placeholder="map, tokens, handout"
            />
          </label>
          <label className="field spanAll">
            <span>Replacement route</span>
            <input
              value={scene.replacement_route}
              onChange={(e) => setScene({ ...scene, replacement_route: e.target.value })}
              placeholder="How do you accomplish this if players bypass the prep?"
            />
          </label>
          <label className="field spanAll">
            <span>If PCs succeed</span>
            <textarea
              value={scene.if_succeed}
              onChange={(e) => setScene({ ...scene, if_succeed: e.target.value })}
              rows="2"
            />
          </label>
          <label className="field spanAll">
            <span>If PCs fail</span>
            <textarea
              value={scene.if_fail}
              onChange={(e) => setScene({ ...scene, if_fail: e.target.value })}
              rows="2"
            />
          </label>
          <label className="field spanAll">
            <span>If PCs ignore it</span>
            <textarea
              value={scene.if_ignore}
              onChange={(e) => setScene({ ...scene, if_ignore: e.target.value })}
              rows="2"
            />
          </label>
          <label className="field spanAll">
            <span>If time is short</span>
            <textarea
              value={scene.if_short}
              onChange={(e) => setScene({ ...scene, if_short: e.target.value })}
              rows="2"
            />
          </label>
        </div>
      </div>

      {/* Section 7: Notes */}
      <div style={{ marginTop: "1.5rem" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#ccc" }}>Notes</h3>
        <div className="formGrid">
          <label className="field spanAll">
            <span>Notes</span>
            <textarea
              value={scene.notes}
              onChange={(e) => setScene({ ...scene, notes: e.target.value })}
              rows="4"
            />
          </label>
        </div>
      </div>

      {/* Draft preview & save */}
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
            <label className="field" style={{ marginBottom: 12 }}>
              <span>Canonical target path</span>
              <input value={sceneTarget} onChange={(e) => setSceneTarget(e.target.value)} />
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
              <pre>{sceneSavePreview.diff}</pre>
            </label>
          )}
        </div>
      )}
      {!sceneDraft && (
        <div className="draftPlaceholder" style={{ marginTop: "2rem" }}>
          Draft appears here after Create Scene Draft
        </div>
      )}
    </div>
  );
}
