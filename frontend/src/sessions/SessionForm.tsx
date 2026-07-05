import { useState } from "react";
import { ChevronDown, Save, Trash } from "lucide-react";
import CustomSelect from "../components/CustomSelect";
import { SessionNoteEditor } from "./SessionNoteEditor";
import type { Session, SessionNote, SessionStatus } from "../types/session";

const STATUS_OPTIONS: { value: SessionStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "ready", label: "Ready" },
  { value: "played", label: "Played" },
  { value: "cancelled", label: "Cancelled" },
  { value: "archived", label: "Archived" },
];

interface FormSession {
  id?: number;
  number: number | string;
  name: string;
  status: SessionStatus;
  date: string;
  notes: string;
  promise: string;
  fit_check: string;
  clue_map: string;
  wrap_capture: string;
  recap_seed: string;
  prep_notes: string;
  wrap_notes: string;
}

const DEFAULT_SESSION: FormSession = {
  number: "",
  name: "",
  status: "planned",
  date: "",
  notes: "",
  promise: "",
  fit_check: "{}",
  clue_map: "[]",
  wrap_capture: "{}",
  recap_seed: "",
  prep_notes: "",
  wrap_notes: "",
};

type NoteDraft = Omit<SessionNote, "id" | "session_id"> | null;

interface SaveData extends Omit<FormSession, "number" | "fit_check" | "clue_map" | "wrap_capture"> {
  number: number;
  date: string | null;
  fit_check: Record<string, unknown>;
  clue_map: Array<Record<string, unknown>>;
  wrap_capture: Record<string, unknown>;
  noteDraft: NoteDraft;
}

interface SessionFormProps {
  session: Partial<Session>;
  onSave: (data: SaveData) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  runAction: unknown;
  onStatusChange: (msg: string) => void;
}

interface CollapsibleSectionProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({ title, children, defaultOpen = false }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details className="scene-section" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="scene-section-summary">
        <ChevronDown size={14} className={`scene-section-chevron${open ? " open" : ""}`} />
        {title}
      </summary>
      <div className="scene-section-body">{children}</div>
    </details>
  );
}

export function SessionForm({ session: initialSession, onSave, onDelete, runAction, onStatusChange }: SessionFormProps) {
  function jsonText(value: unknown, fallback: string) {
    if (typeof value === "string") return value;
    try {
      return JSON.stringify(value ?? JSON.parse(fallback), null, 2);
    } catch {
      return fallback;
    }
  }

  const [session, setSession] = useState<FormSession>({
    ...DEFAULT_SESSION,
    ...initialSession,
    date: initialSession.date ?? "",
    number: initialSession.number ?? "",
    promise: initialSession.promise ?? "",
    notes: initialSession.notes ?? "",
    recap_seed: initialSession.recap_seed ?? "",
    prep_notes: initialSession.prep_notes ?? "",
    wrap_notes: initialSession.wrap_notes ?? "",
    fit_check: jsonText(initialSession.fit_check, "{}"),
    clue_map: jsonText(initialSession.clue_map, "[]"),
    wrap_capture: jsonText(initialSession.wrap_capture, "{}"),
  });
  const [noteDraft, setNoteDraft] = useState<NoteDraft>(null);
  const [jsonError, setJsonError] = useState("");

  function setInput(field: keyof FormSession) {
    return (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setSession((prev) => ({ ...prev, [field]: event.target.value }));
  }

  function set(field: keyof FormSession) {
    return (value: string) => setSession((prev) => ({ ...prev, [field]: value as FormSession[typeof field] }));
  }

  async function handleSave() {
    setJsonError("");
    let fitCheck: Record<string, unknown>;
    let clueMap: Array<Record<string, unknown>>;
    let wrapCapture: Record<string, unknown>;
    try {
      fitCheck = JSON.parse(session.fit_check || "{}");
      clueMap = JSON.parse(session.clue_map || "[]");
      wrapCapture = JSON.parse(session.wrap_capture || "{}");
    } catch (error) {
      setJsonError(error instanceof Error ? error.message : "Invalid structured prep JSON.");
      return;
    }
    if (!Array.isArray(clueMap)) {
      setJsonError("Clue map must be a JSON array.");
      return;
    }
    await onSave({
      ...session,
      number: Number(session.number),
      date: session.date || null,
      fit_check: fitCheck,
      clue_map: clueMap,
      wrap_capture: wrapCapture,
      noteDraft: session.id ? null : noteDraft,
    });
  }

  async function handleDelete() {
    if (session.id) await onDelete(session.id);
  }

  return (
    <>
      <div className="formGrid">
        <label className="field">
          <span>Number</span>
          <input
            type="number"
            min="1"
            value={session.number}
            onChange={setInput("number")}
            placeholder="18"
          />
        </label>
        <label className="field">
          <span>Status</span>
          <CustomSelect
            value={session.status}
            onChange={set("status")}
            options={STATUS_OPTIONS}
            placeholder="Status"
          />
        </label>
        <label className="field">
          <span>Name</span>
          <input
            value={session.name}
            onChange={setInput("name")}
            placeholder="The Iron Keep"
          />
        </label>
        <label className="field">
          <span>Date</span>
          <input type="date" value={session.date || ""} onChange={setInput("date")} />
        </label>
      </div>

      <CollapsibleSection title="Session Prep" defaultOpen={false}>
        <div className="formGrid">
          <label className="field spanAll">
            <span>Promise</span>
            <textarea
              value={session.promise}
              onChange={setInput("promise")}
              rows={2}
              placeholder="What this session must make playable or change"
            />
          </label>
          <label className="field spanAll">
            <span>Notes</span>
            <textarea
              className="session-summary-notes"
              value={session.notes}
              onChange={setInput("notes")}
              rows={3}
              placeholder="Prep notes, recap hook, or session intent"
            />
          </label>
          <label className="field spanAll">
            <span>Prep Notes</span>
            <textarea
              value={session.prep_notes}
              onChange={setInput("prep_notes")}
              rows={4}
              placeholder="Opening, recap script, sensory aids, rules, absence insurance, break check, ending"
            />
          </label>
          <label className="field spanAll">
            <span>Fit Check JSON</span>
            <textarea
              value={session.fit_check}
              onChange={setInput("fit_check")}
              rows={5}
              spellCheck={false}
              placeholder='{"threads":[],"clocks":[],"lanes":[]}'
            />
          </label>
          <label className="field spanAll">
            <span>Clue Map JSON</span>
            <textarea
              value={session.clue_map}
              onChange={setInput("clue_map")}
              rows={6}
              spellCheck={false}
              placeholder='[{"tier":"core","text":"...","holder":"...","found":false,"scene_ids":[]}]'
            />
          </label>
          <label className="field spanAll">
            <span>Wrap Capture JSON</span>
            <textarea
              value={session.wrap_capture}
              onChange={setInput("wrap_capture")}
              rows={6}
              spellCheck={false}
              placeholder='{"actual_endpoint":"","next_session_hook":"","clock_movement":"","lane_changes":""}'
            />
          </label>
          <label className="field spanAll">
            <span>Recap Seed</span>
            <textarea
              value={session.recap_seed}
              onChange={setInput("recap_seed")}
              rows={3}
              placeholder="Generated from the previous session wrap, or edited by hand"
            />
          </label>
          <label className="field spanAll">
            <span>Wrap Notes</span>
            <textarea
              value={session.wrap_notes}
              onChange={setInput("wrap_notes")}
              rows={3}
              placeholder="Rewards, follow-up rulings, actions, and after-session notes"
            />
          </label>
        </div>
        {jsonError && <p style={{ color: "#c97070", fontSize: 13 }}>{jsonError}</p>}
      </CollapsibleSection>

      <SessionNoteEditor
        sessionId={session.id}
        sessionDraft={session}
        runAction={runAction}
        onStatusChange={onStatusChange}
        onPendingChange={setNoteDraft}
      />

      <div className="saveFlow" style={{ marginTop: "var(--space-4)" }}>
        <div className="saveActions">
          {session.id && (
            <button onClick={handleDelete} style={{ color: "#c97070" }}>
              <Trash size={16} /> Delete
            </button>
          )}
          <button onClick={handleSave} className="active">
            <Save size={16} /> Save Session
          </button>
        </div>
      </div>
    </>
  );
}
