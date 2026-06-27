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

export interface Scene {
  id: number;
  title: string;
  type: string;
  status: "Draft" | "Ready" | "Played" | "Cut";
  session_id: number | null;
  description: string;
  location: string[];
  cast: string[];
  clock: string[];
  cuttable: boolean;
  purpose: string;
  pc_pressure: string;
  entry_pressure: string;
  exit_condition: string;
  core_clue: string;
  superior_clue: string;
  optional_clue: string;
  false_lead: string;
  opening_image: string;
  sensory_words: string;
  interactable_objects: string;
  rules_likely: string;
  foundry_needs: string;
  replacement_route: string;
  if_succeed: string;
  if_fail: string;
  if_ignore: string;
  if_short: string;
  notes: string;
  pinned_material: Array<{ title: string; path: string }>;
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
