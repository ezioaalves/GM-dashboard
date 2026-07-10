export type SessionStatus = "planned" | "ready" | "played" | "cancelled" | "archived";

export interface Session {
  id: number;
  number: number;
  name: string;
  status: SessionStatus;
  date: string | null;
  notes: string;
  promise: string;
  fit_check: Record<string, unknown>;
  clue_map: Array<Record<string, unknown>>;
  wrap_capture: Record<string, unknown>;
  recap_seed: string;
  prep_notes: string;
  wrap_notes: string;
  scene_count: number;
  adventures: Array<{ id: number; title: string }>;
}

export interface SessionCreate {
  number: number;
  name?: string;
  status?: SessionStatus;
  date?: string | null;
  notes?: string;
  promise?: string;
  fit_check?: Record<string, unknown>;
  clue_map?: Array<Record<string, unknown>>;
  wrap_capture?: Record<string, unknown>;
  recap_seed?: string;
  prep_notes?: string;
  wrap_notes?: string;
}

export type SessionUpdate = Required<Omit<SessionCreate, never>>;

export interface ClueMapEntry {
  tier: "core" | "superior" | "optional" | "false_lead";
  text: string;
  holder: string;
  location: string;
  found: boolean;
  scene_ids: number[];
  notes: string;
}

export interface WrapCapture {
  what_happened?: string;
  pc_highlights?: Record<string, string>;
  next_session_hook?: string;
  actual_endpoint?: string;
  rewards?: string;
  clock_movement?: string;
  lane_changes?: string;
}

export interface SessionNotePayload {
  scenes: string[];
  npcs_present: string[];
  clues_discovered: string[];
  threads_touched: string[];
  unresolved_questions: string[];
  next_session_hook: string;
  memory: string;
  markdown: string;
  target_path: string;
  status: string;
}

export interface SessionNote {
  id: number;
  session_id: number;
  scenes: string[];
  npcs_present: string[];
  clues_discovered: string[];
  threads_touched: string[];
  unresolved_questions: string[];
  next_session_hook: string;
  memory: string;
  markdown: string;
  target_path: string;
  status: string;
}
