import { useEffect, useState } from "react";
import { FileText, Save } from "lucide-react";
import type { SessionNote } from "../types/session";

type NoteDraft = Omit<SessionNote, "id" | "session_id">;

const EMPTY_NOTE: NoteDraft = {
  scenes: [],
  npcs_present: [],
  clues_discovered: [],
  threads_touched: [],
  unresolved_questions: [],
  next_session_hook: "",
  memory: "",
  markdown: "",
  target_path: "",
  status: "draft",
};

export function SessionNoteEditor({
  sessionId,
  runAction,
  onStatusChange,
  onPendingChange,
}: {
  sessionId?: number;
  sessionDraft: unknown;
  runAction: unknown;
  onStatusChange: (msg: string) => void;
  onPendingChange: (note: NoteDraft) => void;
}) {
  const [note, setNote] = useState<NoteDraft>(EMPTY_NOTE);
  const [error, setError] = useState("");

  useEffect(() => {
    onPendingChange(note);
  }, [note, onPendingChange]);

  useEffect(() => {
    if (!sessionId) return;
    fetch(`/api/sessions/${sessionId}/note`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((body) => {
        if (body) setNote({ ...EMPTY_NOTE, ...body });
      })
      .catch((err) => setError(err.message));
  }, [sessionId]);

  function setText(field: keyof NoteDraft) {
    return (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setNote((prev) => ({ ...prev, [field]: event.target.value }));
    };
  }

  function setList(field: keyof NoteDraft) {
    return (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setNote((prev) => ({
        ...prev,
        [field]: event.target.value.split("\n").map((line) => line.trim()).filter(Boolean),
      }));
    };
  }

  async function run(label: string, fn: () => Promise<void>) {
    if (typeof runAction === "function") {
      await runAction(label, fn);
    } else {
      await fn();
    }
  }

  async function generateNote() {
    if (!sessionId) {
      onStatusChange("Session note will be generated when the session is saved.");
      return;
    }
    await run("Generating note...", async () => {
      const response = await fetch(`/api/sessions/${sessionId}/note/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(note),
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json();
      setNote({ ...EMPTY_NOTE, ...body });
      onStatusChange("Generated markdown.");
    });
  }

  async function saveNote() {
    if (!sessionId) {
      onStatusChange("Session note will be saved with the new session.");
      return;
    }
    await run("Saving note...", async () => {
      const response = await fetch(`/api/sessions/${sessionId}/note`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(note),
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json();
      setNote({ ...EMPTY_NOTE, ...body });
      onStatusChange("Saved note.");
    });
  }

  return (
    <section className="session-note-editor">
      <div className="session-note-header">
        <h3>Session Note</h3>
        <div className="saveActions">
          <button onClick={generateNote}>
            <FileText size={16} /> Generate Note
          </button>
          <button onClick={saveNote}>
            <Save size={16} /> Save Note
          </button>
        </div>
      </div>
      {error && <p className="session-note-error">{error}</p>}
      <div className="session-note-grid">
        <label className="field">
          <span>Scenes</span>
          <textarea value={note.scenes.join("\n")} onChange={setList("scenes")} />
        </label>
        <label className="field">
          <span>Threads</span>
          <textarea value={note.threads_touched.join("\n")} onChange={setList("threads_touched")} />
        </label>
        <label className="field">
          <span>Questions</span>
          <textarea value={note.unresolved_questions.join("\n")} onChange={setList("unresolved_questions")} />
        </label>
        <label className="field">
          <span>Hook</span>
          <textarea value={note.next_session_hook} onChange={setText("next_session_hook")} />
        </label>
        <label className="field spanAll">
          <span>Memory</span>
          <textarea value={note.memory} onChange={setText("memory")} />
        </label>
        <label className="field spanAll">
          <span>Generated markdown</span>
          <textarea
            className="session-note-output"
            value={note.markdown}
            onChange={setText("markdown")}
          />
        </label>
      </div>
    </section>
  );
}
