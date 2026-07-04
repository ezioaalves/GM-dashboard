export interface Thread {
  id: string;
  graph_endpoint_id: string;
  title: string;
  status: "active" | "dormant" | "resolved" | "introduced";
  priority: "low" | "med" | "high" | "urgent";
  arc: string | null;
  theme: string;
  pressure: string;
  stakes: string;
  next_move: string | null;
  clock_label: string | null;
  clock_value: number | null;
  clock_max: number | null;
  unresolved_questions: string[];
  last_touched_at: string | null;
  visibility: string;
  freshness_state: string;
  review_status: string;
  factions: string[];
  sessions: number[];
  vault_path: string | null;
  body: string | null;
  stale_state: ThreadStaleState;
}

export interface ThreadStaleState {
  state: "current" | "needs_direction" | "stale";
  age_days: number | null;
  reasons: string[];
}

export interface ThreadLinkedEntity {
  id: string;
  graph_endpoint_id: string;
  slug: string;
  title: string;
  entity_type: string;
  summary: string;
  freshness_state: string;
}

export interface ThreadLinkedSession {
  id: number;
  graph_endpoint_id: string;
  number: number;
  name: string;
  status: string;
  date: string | null;
  freshness_state: string;
}

export interface ThreadLinkedScene {
  id: number;
  graph_endpoint_id: string;
  title: string;
  status: string;
  session_id: number | null;
  placement: string;
  purpose: string;
  freshness_state: string;
}

export interface ThreadRelationship {
  id: string;
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  unresolved_target: string;
  relationship_type: string;
  direction: string;
  provenance: string;
  confidence: number | null;
  context: string;
  review_status: string;
}

export interface ThreadDetail extends Thread {
  linked: {
    entities: ThreadLinkedEntity[];
    sessions: ThreadLinkedSession[];
    scenes: ThreadLinkedScene[];
    relationships: ThreadRelationship[];
  };
}

export interface ThreadSummary {
  total: number;
  active: number;
  stale: number;
  needs_direction: number;
  high_priority: number;
  next_moves: Thread[];
  next_campaign_move: Thread | null;
  active_pressure: Thread[];
  stale_threads: Thread[];
}

export interface ThreadCreate {
  id: string;
  title: string;
  status: Thread["status"];
  priority?: Thread["priority"];
  arc?: string;
  theme?: string;
  pressure?: string;
  stakes?: string;
  next_move?: string | null;
  clock_label?: string | null;
  clock_value?: number | null;
  clock_max?: number | null;
  unresolved_questions?: string[];
  last_touched_at?: string | null;
  freshness_state?: string;
  factions?: string[];
  sessions?: number[];
  body?: string;
}

export type ThreadUpdate = Partial<Omit<ThreadCreate, "id">>;
