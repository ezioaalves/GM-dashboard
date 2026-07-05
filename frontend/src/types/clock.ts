export type ClockKind = "progress" | "countdown";
export type ClockLifecycle = "active" | "resolved" | "abandoned";
export type MirrorState = "not_mirrored" | "mirrored" | "failed" | "missing_mirror";
export type ClockCausedBy = "manual" | "rule" | "import" | "drift_adopt";

export interface SegmentLabel {
  index: number;
  label: string;
}

export interface ClockMirror {
  state: MirrorState;
  foundry_clock_id_test: string; // "" when not mirrored to that env
  foundry_clock_id_prod: string;
  last_mirrored_at: string | null;
}

export interface Clock {
  id: string;
  graph_endpoint_id: string;
  name: string;
  description: string;
  kind: ClockKind;
  segments: number;
  filled: number;
  lifecycle: ClockLifecycle;
  resolution: string;
  resolved_at: string | null;
  origin: string;
  segment_labels: SegmentLabel[];
  visibility: string;
  freshness_state: string;
  review_status: string;
  mirror: ClockMirror;
  created_at: string;
  updated_at: string;
}

export interface ClockLink {
  id: string;
  target_type: string;
  target_id: string; // graph_endpoint_id of the linked entity
  relationship_type: string;
}

export interface ClockDetail extends Clock {
  links: ClockLink[];
}

export interface ClockTick {
  id: string;
  clock_id: string;
  delta: number;
  filled_before: number;
  filled_after: number;
  reason: string;
  caused_by: ClockCausedBy;
  rule_id: string | null;
  rule_name: string | null;
  rule_title: string | null;
  trigger_fire_id: string;
  hop_depth: number;
  created_by: string | null;
  created_at: string;
}

export interface AppliedTick {
  clock_id: string;
  delta: number;
  filled_before: number;
  filled_after: number;
  reason: string;
  caused_by: ClockCausedBy;
  rule_id: string | null;
  hop_depth: number;
  events: string[];
  trigger_fire_id: string;
}

export interface SkippedEffect {
  clock_id: string;
  delta: number;
  rule_id: string | null;
  hop_depth: number;
  why: string;
}

export interface FireResult {
  trigger_fire_id: string;
  dry_run: boolean;
  applied: AppliedTick[];
  skipped: SkippedEffect[];
  guard_trips: string[];
  clocks: Record<string, { filled: number; segments: number }>;
}

export interface ClockCreate {
  name: string;
  kind?: ClockKind;
  segments: number;
  description?: string;
  segment_labels?: SegmentLabel[];
  visibility?: string;
}

export interface ClockUpdate {
  name?: string;
  description?: string;
  segments?: number;
  segment_labels?: SegmentLabel[];
  visibility?: string;
}

export interface LifecycleUpdate {
  lifecycle: ClockLifecycle;
  resolution?: string;
}

export interface TickRequest {
  delta: number;
  reason: string;
}

export interface ClockLinkRequest {
  target_endpoint: string;
  relationship_type?: string;
}

export interface CascadeRule {
  id: string;
  name: string;
  title: string;
  description: string;
  trigger_kind: "manual" | "clock_event";
  trigger_clock_id: string | null;
  trigger_event: string | null;
  condition: unknown; // DSL JSON; builder-owned
  effects: { clock_id: string; delta: number; reason_template: string }[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CascadeRuleCreate {
  name: string;
  title?: string;
  description?: string;
  trigger_kind?: "manual" | "clock_event";
  trigger_clock_id?: string | null;
  trigger_event?: string | null;
  condition?: unknown;
  effects: { clock_id: string; delta: number; reason_template: string }[];
  enabled?: boolean;
}

export type CascadeRuleUpdate = Partial<CascadeRuleCreate>;

export interface FireRequest {
  dry_run?: boolean;
  trigger_note?: string;
}

export interface DriftVerdict {
  clock_id: string;
  kind: "value_drift" | "missing_mirror";
  fields?: Record<string, { engine: unknown; foundry: unknown }>;
}

// --- Mirror / drift (Tasks 9-10, not yet implemented server-side) ---
// Shapes below are speculative: derived from the design plan
// (docs/superpowers/plans/2026-07-04-gm-dashboard-clock-engine.md, Task 9,
// "Add mirror + drift routes to clocks_router.py") rather than verified
// against shipped code. Re-verify once Tasks 9-10 land.

export interface MirrorRequest {
  env: "test" | "prod";
  action?: "establish" | "unmirror";
}

export interface MirrorReviewResult {
  id: string;
  review_status: string;
}

export interface DriftCheckResult {
  env: string;
  checked: number;
  verdicts: DriftVerdict[];
}
