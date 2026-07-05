import { useRef, useState, useEffect } from "react";
import { ChevronDown, Plus, Save, Trash } from "lucide-react";
import CustomSelect from "../components/CustomSelect";
import { useScenesQuery } from "../api/scenes";
import { useClocksQuery } from "../api/clocks";
import { SessionNoteEditor } from "./SessionNoteEditor";
import type { Session, SessionNote, SessionStatus } from "../types/session";

const STATUS_OPTIONS: { value: SessionStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "ready", label: "Ready" },
  { value: "played", label: "Played" },
  { value: "cancelled", label: "Cancelled" },
  { value: "archived", label: "Archived" },
];

const PC_LANES = ["Ikazuchi", "Kubo", "Dan", "Suigin"];

const SESSION_MODE_OPTIONS = [
  { value: "", label: "— Select —" },
  { value: "mission", label: "Mission" },
  { value: "training", label: "Training" },
  { value: "social", label: "Social" },
  { value: "investigation", label: "Investigation" },
  { value: "downtime", label: "Downtime" },
  { value: "crisis", label: "Crisis" },
  { value: "mixed", label: "Mixed" },
];

const CLUE_TIER_OPTIONS = [
  { value: "core", label: "Core" },
  { value: "superior", label: "Superior" },
  { value: "optional", label: "Optional" },
  { value: "false-lead", label: "False lead" },
  { value: "back-door", label: "Back door" },
];

// ── Structured Session Prep sub-shapes ──────────────────────────────────────────

interface FitCheckForm {
  campaign_frame: string;
  current_arc: string;
  session_mode: string;
  pc_lanes: Record<string, string>;
  active_clocks: string[];
  npc_relationships: string;
  mechanics_likely: string;
  safety_flags: string;
}

interface ClueMapRow {
  tier: string;
  text: string;
  holder: string;
  location: string;
  found: boolean;
  scene_ids: number[];
  notes: string;
}

interface WrapCaptureForm {
  actual_endpoint: string;
  feedback_questions: string;
  rewards: string;
  loot_resources: string;
  injuries_conditions: string;
  npc_attitude_changes: string;
  clock_movement: string;
  lane_changes: string;
  rulings_to_review: string;
  next_session_hook: string;
}

const EMPTY_FIT_CHECK: FitCheckForm = {
  campaign_frame: "",
  current_arc: "",
  session_mode: "",
  pc_lanes: {},
  active_clocks: [],
  npc_relationships: "",
  mechanics_likely: "",
  safety_flags: "",
};

const EMPTY_WRAP_CAPTURE: WrapCaptureForm = {
  actual_endpoint: "",
  feedback_questions: "",
  rewards: "",
  loot_resources: "",
  injuries_conditions: "",
  npc_attitude_changes: "",
  clock_movement: "",
  lane_changes: "",
  rulings_to_review: "",
  next_session_hook: "",
};

const EMPTY_CLUE_ROW: ClueMapRow = {
  tier: "core",
  text: "",
  holder: "",
  location: "",
  found: false,
  scene_ids: [],
  notes: "",
};

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function toFitCheckForm(raw: unknown): FitCheckForm {
  const source = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const lanesSource = (source.pc_lanes && typeof source.pc_lanes === "object" ? source.pc_lanes : {}) as Record<string, unknown>;
  const pc_lanes: Record<string, string> = {};
  for (const pc of PC_LANES) pc_lanes[pc] = str(lanesSource[pc]);
  return {
    campaign_frame: str(source.campaign_frame),
    current_arc: str(source.current_arc),
    session_mode: str(source.session_mode),
    pc_lanes,
    active_clocks: Array.isArray(source.active_clocks) ? source.active_clocks.map(String) : [],
    npc_relationships: str(source.npc_relationships),
    mechanics_likely: str(source.mechanics_likely),
    safety_flags: str(source.safety_flags),
  };
}

function toWrapCaptureForm(raw: unknown): WrapCaptureForm {
  const source = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  return {
    actual_endpoint: str(source.actual_endpoint),
    feedback_questions: str(source.feedback_questions),
    rewards: str(source.rewards),
    loot_resources: str(source.loot_resources),
    injuries_conditions: str(source.injuries_conditions),
    npc_attitude_changes: str(source.npc_attitude_changes),
    clock_movement: str(source.clock_movement),
    lane_changes: str(source.lane_changes),
    rulings_to_review: str(source.rulings_to_review),
    next_session_hook: str(source.next_session_hook),
  };
}

function toClueMapRows(raw: unknown): ClueMapRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((entry) => {
    const source = (entry && typeof entry === "object" ? entry : {}) as Record<string, unknown>;
    return {
      tier: str(source.tier) || "core",
      text: str(source.text),
      holder: str(source.holder),
      location: str(source.location),
      found: Boolean(source.found),
      scene_ids: Array.isArray(source.scene_ids) ? source.scene_ids.map(Number) : [],
      notes: str(source.notes),
    };
  });
}

interface FormSession {
  id?: number;
  number: number | string;
  name: string;
  status: SessionStatus;
  date: string;
  notes: string;
  promise: string;
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
  recap_seed: "",
  prep_notes: "",
  wrap_notes: "",
};

type NoteDraft = Omit<SessionNote, "id" | "session_id"> | null;

interface SaveData extends Omit<FormSession, "number"> {
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

// A small free-text tag picker for annotation fields (e.g. "active clocks")
// that reference other entities by name rather than a strict foreign key.
interface TagPickerProps {
  value: string[];
  onChange: (val: string[]) => void;
  suggestions: string[];
  placeholder: string;
}

function TagPicker({ value, onChange, suggestions, placeholder }: TagPickerProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selected = new Set(value);
  const filtered = suggestions.filter(
    (s) => !selected.has(s) && s.toLowerCase().includes(query.toLowerCase())
  );
  const canAddFreeText = query.trim() && !selected.has(query.trim()) && !suggestions.includes(query.trim());

  function add(item: string) {
    onChange([...value, item]);
    setQuery("");
  }

  return (
    <div className="multi-tag-select" ref={ref}>
      <div className="multi-tag-input-row" onClick={() => setOpen(true)}>
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
          className="tag-input"
          value={query}
          placeholder={value.length === 0 ? placeholder : ""}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) { e.preventDefault(); add(query.trim()); }
            if (e.key === "Backspace" && !query && value.length) onChange(value.slice(0, -1));
          }}
        />
      </div>
      {open && (filtered.length > 0 || canAddFreeText) && (
        <ul className="custom-select-dropdown">
          {filtered.map((item) => (
            <li key={item} className="custom-select-option" onMouseDown={() => add(item)}>{item}</li>
          ))}
          {canAddFreeText && (
            <li className="custom-select-option" onMouseDown={() => add(query.trim())}>
              + Use "{query.trim()}"
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

export function SessionForm({ session: initialSession, onSave, onDelete, runAction, onStatusChange }: SessionFormProps) {
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
  });
  const [fitCheck, setFitCheck] = useState<FitCheckForm>(toFitCheckForm(initialSession.fit_check));
  const [clueMap, setClueMap] = useState<ClueMapRow[]>(toClueMapRows(initialSession.clue_map));
  const [wrapCapture, setWrapCapture] = useState<WrapCaptureForm>(toWrapCaptureForm(initialSession.wrap_capture));
  const [noteDraft, setNoteDraft] = useState<NoteDraft>(null);
  const [clueError, setClueError] = useState("");

  const { data: sessionScenes = [] } = useScenesQuery(session.id ?? null);
  const { data: activeClocks = [] } = useClocksQuery({ lifecycle: "active" });
  const clockNames = activeClocks.map((c) => c.name);

  function setInput(field: keyof FormSession) {
    return (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setSession((prev) => ({ ...prev, [field]: event.target.value }));
  }

  function set(field: keyof FormSession) {
    return (value: string) => setSession((prev) => ({ ...prev, [field]: value as FormSession[typeof field] }));
  }

  function setFitField<K extends keyof FitCheckForm>(field: K, value: FitCheckForm[K]) {
    setFitCheck((prev) => ({ ...prev, [field]: value }));
  }

  function setLane(pc: string, value: string) {
    setFitCheck((prev) => ({ ...prev, pc_lanes: { ...prev.pc_lanes, [pc]: value } }));
  }

  function setWrapField<K extends keyof WrapCaptureForm>(field: K, value: WrapCaptureForm[K]) {
    setWrapCapture((prev) => ({ ...prev, [field]: value }));
  }

  function addClueRow() {
    setClueMap((prev) => [...prev, { ...EMPTY_CLUE_ROW }]);
  }

  function removeClueRow(index: number) {
    setClueMap((prev) => prev.filter((_, i) => i !== index));
  }

  function updateClueRow(index: number, patch: Partial<ClueMapRow>) {
    setClueMap((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function toggleClueScene(index: number, sceneId: number) {
    setClueMap((prev) =>
      prev.map((row, i) => {
        if (i !== index) return row;
        const has = row.scene_ids.includes(sceneId);
        return { ...row, scene_ids: has ? row.scene_ids.filter((id) => id !== sceneId) : [...row.scene_ids, sceneId] };
      })
    );
  }

  async function handleSave() {
    setClueError("");
    const filledClues = clueMap.filter((row) => row.text.trim());
    const invalid = filledClues.find((row) => !row.holder.trim() && !row.location.trim());
    if (invalid) {
      setClueError("Every clue needs a holder or a location.");
      return;
    }
    await onSave({
      ...session,
      number: Number(session.number),
      date: session.date || null,
      fit_check: fitCheck as unknown as Record<string, unknown>,
      clue_map: filledClues as unknown as Array<Record<string, unknown>>,
      wrap_capture: wrapCapture as unknown as Record<string, unknown>,
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
              placeholder="This session is about the 13th Tanto confronting ______ so that ______ changes."
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
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Fit Check" defaultOpen={false}>
        <div className="formGrid">
          <label className="field">
            <span>Campaign frame</span>
            <input
              value={fitCheck.campaign_frame}
              onChange={(e) => setFitField("campaign_frame", e.target.value)}
              placeholder="What this session must fit into"
            />
          </label>
          <label className="field">
            <span>Current arc</span>
            <input
              value={fitCheck.current_arc}
              onChange={(e) => setFitField("current_arc", e.target.value)}
              placeholder="Training Arc"
            />
          </label>
          <label className="field">
            <span>Session mode</span>
            <CustomSelect
              value={fitCheck.session_mode}
              onChange={(v) => setFitField("session_mode", v)}
              options={SESSION_MODE_OPTIONS}
              placeholder="— Select —"
            />
          </label>
          <label className="field spanAll">
            <span>Active clocks</span>
            <TagPicker
              value={fitCheck.active_clocks}
              onChange={(v) => setFitField("active_clocks", v)}
              suggestions={clockNames}
              placeholder="Search or add a clock…"
            />
          </label>
          <div className="field spanAll">
            <span>PC lanes pressured</span>
            <div className="formGrid">
              {PC_LANES.map((pc) => (
                <label key={pc} className="field">
                  <span>{pc}</span>
                  <input
                    value={fitCheck.pc_lanes[pc] ?? ""}
                    onChange={(e) => setLane(pc, e.target.value)}
                    placeholder="How this PC's lane gets pressured"
                  />
                </label>
              ))}
            </div>
          </div>
          <label className="field spanAll">
            <span>NPC relationships likely to change</span>
            <textarea
              value={fitCheck.npc_relationships}
              onChange={(e) => setFitField("npc_relationships", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field spanAll">
            <span>Mechanics likely to matter</span>
            <textarea
              value={fitCheck.mechanics_likely}
              onChange={(e) => setFitField("mechanics_likely", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field spanAll">
            <span>Safety/tone flags</span>
            <textarea
              value={fitCheck.safety_flags}
              onChange={(e) => setFitField("safety_flags", e.target.value)}
              rows={2}
            />
          </label>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title={`Clue Map (${clueMap.length})`} defaultOpen={false}>
        <div className="clue-map-rows">
          {clueMap.map((row, index) => (
            <div key={index} className="clue-map-row">
              <div className="formGrid">
                <label className="field">
                  <span>Tier</span>
                  <CustomSelect
                    value={row.tier}
                    onChange={(v) => updateClueRow(index, { tier: v })}
                    options={CLUE_TIER_OPTIONS}
                    placeholder="Tier"
                  />
                </label>
                <label className="field">
                  <span>Found</span>
                  <label className="checkbox-inline">
                    <input
                      type="checkbox"
                      checked={row.found}
                      onChange={(e) => updateClueRow(index, { found: e.target.checked })}
                    />
                    Discovered at the table
                  </label>
                </label>
                <label className="field">
                  <span>Holder</span>
                  <input
                    value={row.holder}
                    onChange={(e) => updateClueRow(index, { holder: e.target.value })}
                    placeholder="Who has this clue?"
                  />
                </label>
                <label className="field">
                  <span>Location</span>
                  <input
                    value={row.location}
                    onChange={(e) => updateClueRow(index, { location: e.target.value })}
                    placeholder="Where is this clue?"
                  />
                </label>
                <label className="field spanAll">
                  <span>Clue</span>
                  <textarea
                    value={row.text}
                    onChange={(e) => updateClueRow(index, { text: e.target.value })}
                    rows={2}
                    placeholder="What the players actually learn"
                  />
                </label>
                {sessionScenes.length > 0 && (
                  <div className="field spanAll">
                    <span>Linked scenes</span>
                    <div className="clue-scene-links">
                      {sessionScenes.map((scene) => (
                        <label key={scene.id} className="checkbox-inline">
                          <input
                            type="checkbox"
                            checked={row.scene_ids.includes(scene.id)}
                            onChange={() => toggleClueScene(index, scene.id)}
                          />
                          {scene.title || `Scene ${scene.id}`}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
                <label className="field spanAll">
                  <span>Notes</span>
                  <textarea
                    value={row.notes}
                    onChange={(e) => updateClueRow(index, { notes: e.target.value })}
                    rows={1}
                  />
                </label>
              </div>
              <button type="button" onClick={() => removeClueRow(index)} style={{ color: "#c97070" }}>
                <Trash size={14} /> Remove clue
              </button>
            </div>
          ))}
        </div>
        <button type="button" onClick={addClueRow}>
          <Plus size={14} /> Add clue
        </button>
        {clueError && <p style={{ color: "#c97070", fontSize: 13 }}>{clueError}</p>}
      </CollapsibleSection>

      <CollapsibleSection title="Wrap Capture" defaultOpen={false}>
        <div className="formGrid">
          <label className="field spanAll">
            <span>Actual endpoint</span>
            <input
              value={wrapCapture.actual_endpoint}
              onChange={(e) => setWrapField("actual_endpoint", e.target.value)}
              placeholder="Where the session actually landed"
            />
          </label>
          <label className="field spanAll">
            <span>Feedback questions</span>
            <textarea
              value={wrapCapture.feedback_questions}
              onChange={(e) => setWrapField("feedback_questions", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field">
            <span>Rewards/advancement</span>
            <textarea
              value={wrapCapture.rewards}
              onChange={(e) => setWrapField("rewards", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field">
            <span>Loot/resources</span>
            <textarea
              value={wrapCapture.loot_resources}
              onChange={(e) => setWrapField("loot_resources", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field">
            <span>Injuries/conditions</span>
            <textarea
              value={wrapCapture.injuries_conditions}
              onChange={(e) => setWrapField("injuries_conditions", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field">
            <span>NPC attitude changes</span>
            <textarea
              value={wrapCapture.npc_attitude_changes}
              onChange={(e) => setWrapField("npc_attitude_changes", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field">
            <span>Clock movement</span>
            <textarea
              value={wrapCapture.clock_movement}
              onChange={(e) => setWrapField("clock_movement", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field">
            <span>PC lane changes</span>
            <textarea
              value={wrapCapture.lane_changes}
              onChange={(e) => setWrapField("lane_changes", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field spanAll">
            <span>Rulings to review</span>
            <textarea
              value={wrapCapture.rulings_to_review}
              onChange={(e) => setWrapField("rulings_to_review", e.target.value)}
              rows={2}
            />
          </label>
          <label className="field spanAll">
            <span>Next-session hook</span>
            <textarea
              value={wrapCapture.next_session_hook}
              onChange={(e) => setWrapField("next_session_hook", e.target.value)}
              rows={2}
              placeholder="Pre-fills the next session's recap seed"
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
              placeholder="Anything else after-session that doesn't fit the fields above"
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
