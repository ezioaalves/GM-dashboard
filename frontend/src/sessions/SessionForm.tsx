import { useState } from "react";
import { ChevronDown, Save, Trash } from "lucide-react";
import CustomSelect from "../components/CustomSelect";
import { SessionNoteEditor } from "./SessionNoteEditor";
import type { Session, SessionNote } from "../types/session";

type SessionStatus = "Planned" | "Active" | "Played";

const STATUS_OPTIONS: { value: SessionStatus; label: string }[] = [
  { value: "Planned", label: "Planned" },
  { value: "Active", label: "Active" },
  { value: "Played", label: "Played" },
];

interface FormSession {
  id?: number;
  number: number | string;
  name: string;
  status: SessionStatus;
  date: string;
  notes: string;
}

const DEFAULT_SESSION: FormSession = {
  number: "",
  name: "",
  status: "Planned",
  date: "",
  notes: "",
};

type NoteDraft = Omit<SessionNote, "id" | "session_id"> | null;

interface SaveData extends Omit<FormSession, "number"> {
  number: number;
  date: string | null;
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
  const [session, setSession] = useState<FormSession>({
    ...DEFAULT_SESSION,
    ...initialSession,
    date: initialSession.date ?? "",
    number: initialSession.number ?? "",
  });
  const [noteDraft, setNoteDraft] = useState<NoteDraft>(null);

  function setInput(field: keyof FormSession) {
    return (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setSession((prev) => ({ ...prev, [field]: event.target.value }));
  }

  function set(field: keyof FormSession) {
    return (value: string) => setSession((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSave() {
    await onSave({
      ...session,
      number: Number(session.number),
      date: session.date || null,
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
            <span>Notes</span>
            <textarea
              className="session-summary-notes"
              value={session.notes}
              onChange={setInput("notes")}
              rows={3}
              placeholder="Prep notes, recap hook, or session intent"
            />
          </label>
        </div>
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
