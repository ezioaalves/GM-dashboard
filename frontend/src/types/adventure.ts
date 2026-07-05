export type AdventureStatus = "draft" | "ready" | "played" | "archived";

/** Deck-card summary shape returned by GET /api/adventures — no JSONB blobs. */
export interface AdventureListItem {
  id: number;
  graph_endpoint_id: string;
  title: string;
  status: AdventureStatus;
  mode: string;
  current_arc: string;
  pitch: string;
  session_count: number;
}

export interface Adventure {
  id: number;
  graph_endpoint_id: string;
  title: string;
  status: AdventureStatus;
  current_arc: string;
  pitch: string;
  mode: string;
  tone_rule: string;
  safety_flags: string;
  feel_target: string;
  feel_avoid: string;
  stakes: Record<string, unknown>;
  location: Record<string, unknown>;
  spine: Array<{ label: string; text: string }>;
  clue_map: Record<string, unknown>;
  foundry_needs: Record<string, unknown>;
  rules_notes: Record<string, unknown>;
  visibility: string;
  freshness_state: string;
  review_status: string;
  session_count: number;
}

export interface AdventurePcPressureRow {
  id: number;
  pc_id: number;
  pressure: string;
  growth: string;
  cost: string;
  sort_order: number;
}

export interface AdventureRewardRow {
  id: number;
  name: string;
  type: string;
  who_cares: string;
  mechanical_note: string;
  future_hook: string;
  sort_order: number;
}

export interface AdventureClockLinkRow {
  id: number;
  clock_id: string | null;
  thread_id: string | null;
  how_it_appears: string;
  advance_trigger: string;
  visible_impact: string;
}

export interface AdventureEncounterRow {
  id: number;
  name: string;
  objective: string;
  opposition: string;
  terrain_constraint: string;
  what_changes: string;
  sort_order: number;
}

export interface AdventureCastRow {
  id: number;
  npc_id: number;
  role: string;
  wants_now: string;
  hides: string;
  if_helped: string;
  if_crossed: string;
  sort_order: number;
}

export interface AdventureDetail extends Adventure {
  pc_pressure: AdventurePcPressureRow[];
  rewards: AdventureRewardRow[];
  clock_links: AdventureClockLinkRow[];
  encounters: AdventureEncounterRow[];
  cast: AdventureCastRow[];
  sessions: Array<{ id: number; title: string }>;
}

export type AdventureCreate = Partial<
  Omit<Adventure, "id" | "graph_endpoint_id" | "session_count" | "visibility" | "freshness_state" | "review_status">
>;

export type AdventurePatch = AdventureCreate & {
  visibility?: string;
  freshness_state?: string;
  review_status?: string;
};
