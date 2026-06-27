export interface Session {
  id: number;
  number: number;
  name: string;
  status: "Planned" | "Active" | "Played";
  date: string | null;
  notes: string;
  scene_count: number;
}

export interface SessionCreate {
  number: number;
  name?: string;
  status?: "Planned" | "Active" | "Played";
  date?: string | null;
  notes?: string;
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
