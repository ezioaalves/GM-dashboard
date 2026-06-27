import React, { useEffect, useState } from "react";
import { Eye, NotebookPen, Save } from "lucide-react";
import { marked } from "marked";

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
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitLines(value) {
  return value
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export default function SessionNote({ onStatusChange, runAction }) {
  const [draft, setDraft] = useState(null);
  const [draftText, setDraftText] = useState("");
  const [draftTarget, setDraftTarget] = useState("");
  const [savePreview, setSavePreview] = useState(null);
  const [draftTab, setDraftTab] = useState("edit");

  const [contextData, setContextData] = useState(null);
  const [contextError, setContextError] = useState("");

  const [form, setForm] = useState({
    scenes: "",
    npcs_present: "",
    clues_discovered: "",
    threads_touched: "",
    unresolved_questions: "",
    next_session_hook: "",
    memory: "",
  });

  useEffect(() => {
    fetch("/api/capture/session-note/context")
      .then((r) => r.json())
      .then((json) => {
        setContextData(json);
        if (json.npc_list?.length > 0) {
          setForm((f) => ({ ...f, npcs_present: json.npc_list.join(", ") }));
        }
      })
      .catch((err) => setContextError(`Could not load context: ${err.message}`));
  }, []);

  function field(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function generate() {
    await runAction("Generating session draft...", async () => {
      const json = await postJson("/api/capture/session-note", {
        memory: form.memory,
        scenes: splitLines(form.scenes),
        npcs_present: splitList(form.npcs_present),
        clues_discovered: splitLines(form.clues_discovered),
        threads_touched: splitLines(form.threads_touched),
        unresolved_questions: splitLines(form.unresolved_questions),
        next_session_hook: form.next_session_hook,
      });
      setDraft(json);
      setDraftText(json.markdown);
      setDraftTarget(json.default_target_path);
      setSavePreview(null);
      setDraftTab("edit");
      onStatusChange(`Session draft written to ${json.path}`);
    });
  }

  async function previewSave() {
    if (!draft) return;
    await runAction(`Preparing diff for ${draftTarget}...`, async () => {
      const json = await postJson(`/api/drafts/${draft.id}/preview`, {
        target_path: draftTarget,
        markdown: draftText,
      });
      setSavePreview(json);
      onStatusChange(`Preview ready for ${json.path}.`);
    });
  }

  async function confirmSave() {
    if (!draft) return;
    await runAction(`Saving ${draftTarget}...`, async () => {
      const json = await postJson(`/api/drafts/${draft.id}/save`, {
        target_path: draftTarget,
        markdown: draftText,
        confirm: true,
      });
      setSavePreview(json);
      onStatusChange(`Canonical Markdown saved to ${json.path}.`);
    });
  }

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>Session Note</h2>
          <p>Fill in what you remember — generate draft — review — save.</p>
        </div>
        <button onClick={generate}>
          <NotebookPen size={16} /> Generate Draft
        </button>
      </div>

      <div className="sessionThreeCol">
        {/* Left: vault context */}
        <div className="contextPanel">
          {contextError && <p className="sn-context-error">{contextError}</p>}
          {!contextData && !contextError && <p className="contextText">Loading context…</p>}
          {contextData && (
            <>
              <div className="contextSection">
                <div className="contextLabel">Latest session</div>
                {contextData.latest_session ? (
                  <p className="contextText">
                    Session {contextData.latest_session.session}: {contextData.latest_session.title}
                    {contextData.latest_session.date ? ` (${contextData.latest_session.date})` : ""}
                  </p>
                ) : (
                  <p className="contextText">No session logs found.</p>
                )}
              </div>

              {contextData.npc_list?.length > 0 && (
                <div className="contextSection">
                  <div className="contextLabel">Last session NPCs</div>
                  <p className="contextText">{contextData.npc_list.join(", ")}</p>
                </div>
              )}

              {contextData.live_prep_excerpt && (
                <div className="contextSection">
                  <div className="contextLabel">Live prep</div>
                  <p className="contextText">
                    {contextData.live_prep_excerpt.slice(0, 400)}
                    {contextData.live_prep_excerpt.length > 400 ? "…" : ""}
                  </p>
                </div>
              )}

              {contextData.active_threads?.length > 0 && (
                <div className="contextSection">
                  <div className="contextLabel">
                    Active threads ({contextData.active_threads.length})
                  </div>
                  {contextData.active_threads.map((t) => (
                    <div key={t.id} className="sn-thread-item">
                      <div className="sn-thread-title">{t.title}</div>
                      {t.next_move && <div className="contextText">{t.next_move}</div>}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Middle: recovery form */}
        <div className="sn-form-col">
          <Field label="Scenes (one per line, in order)">
            <textarea
              value={form.scenes}
              onChange={field("scenes")}
              placeholder={"Party escapes the forest\nDan spots the patrol beacon"}
              rows="4"
            />
          </Field>
          <Field label="NPCs present (comma-separated)">
            <input
              value={form.npcs_present}
              onChange={field("npcs_present")}
              placeholder="Dan, Ikazuchi, Suigin"
            />
          </Field>
          <Field label="Clues discovered (one per line)">
            <textarea value={form.clues_discovered} onChange={field("clues_discovered")} rows="3" />
          </Field>
          <Field label="Threads touched (one per line)">
            <textarea value={form.threads_touched} onChange={field("threads_touched")} rows="3" />
          </Field>
          <Field label="Unresolved questions (one per line)">
            <textarea
              value={form.unresolved_questions}
              onChange={field("unresolved_questions")}
              rows="3"
            />
          </Field>
          <Field label="Hook for next session">
            <input
              value={form.next_session_hook}
              onChange={field("next_session_hook")}
              placeholder="Party emerges from the forest at dawn"
            />
          </Field>
          <Field label="GM memory / notes">
            <textarea
              value={form.memory}
              onChange={field("memory")}
              placeholder="Rough fragments fine — becomes the Continuity notes section."
              rows="4"
            />
          </Field>
        </div>

        {/* Right: draft tabs */}
        {draft ? (
          <div className="sn-draft-col">
            <div>
              <div className="draftTabs">
                <button
                  className={draftTab === "edit" ? "active" : ""}
                  onClick={() => setDraftTab("edit")}
                >
                  Edit
                </button>
                <button
                  className={draftTab === "preview" ? "active" : ""}
                  onClick={() => setDraftTab("preview")}
                >
                  Preview
                </button>
                <button
                  className={draftTab === "diff" ? "active" : ""}
                  onClick={() => setDraftTab("diff")}
                >
                  Diff
                </button>
              </div>

              {draftTab === "edit" && (
                <Field label={`Draft — ${draft.path}`}>
                  <textarea
                    className="sn-draft-tall"
                    value={draftText}
                    onChange={(e) => setDraftText(e.target.value)}
                  />
                </Field>
              )}

              {draftTab === "preview" && (
                <div>
                  <div className="contextLabel sn-preview-label">Rendered preview</div>
                  <div
                    className="markdownPreview"
                    dangerouslySetInnerHTML={{ __html: marked.parse(draftText) }}
                  />
                </div>
              )}

              {draftTab === "diff" && (
                <Field label={savePreview ? "Canonical diff" : "Initial draft diff"}>
                  <pre className="sn-draft-tall">
                    {(savePreview && savePreview.diff) || draft.diff}
                  </pre>
                </Field>
              )}
            </div>

            <div className="saveFlow">
              <Field label="Canonical target path">
                <input
                  value={draftTarget}
                  onChange={(e) => setDraftTarget(e.target.value)}
                />
              </Field>
              <div className="saveActions">
                <button onClick={previewSave}>
                  <Eye size={16} /> Preview Save
                </button>
                <button onClick={confirmSave}>
                  <Save size={16} /> Confirm Save
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="draftPlaceholder">Draft appears here after Generate</div>
        )}
      </div>
    </div>
  );
}
