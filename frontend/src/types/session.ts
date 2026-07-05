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
