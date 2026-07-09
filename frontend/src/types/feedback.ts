export type FeedbackCadence = "quick_check" | "arc_review" | "private_checkin";
export type ActionItemStatus = "open" | "done" | "dropped";

export interface FeedbackActionItem {
  id: number;
  item: string;
  owner: string;
  follow_up: string;
  status: ActionItemStatus;
  sort_order: number;
}

export interface FeedbackEntry {
  id: number;
  session_number: number | null;
  cadence: FeedbackCadence;
  players_present: string;
  more_of: string;
  less_of: string;
  clarify: string;
  notes: string;
  recorded_at: string | null;
  action_items: FeedbackActionItem[];
}

export interface FeedbackEntryCreate {
  session_number?: number | null;
  cadence?: FeedbackCadence;
  players_present?: string;
  more_of?: string;
  less_of?: string;
  clarify?: string;
  notes?: string;
}

export type FeedbackEntryPatch = Partial<FeedbackEntryCreate>;

export interface ActionItemCreate {
  item?: string;
  owner?: string;
  follow_up?: string;
  status?: ActionItemStatus;
  sort_order?: number;
}

export type ActionItemPatch = Partial<ActionItemCreate>;

export interface FeedbackOverdueItem {
  cadence: FeedbackCadence;
  last_session_number: number | null;
  sessions_since_last: number;
  threshold: number;
}
