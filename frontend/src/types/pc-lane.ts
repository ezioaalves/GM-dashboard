export type PcLaneStatus = "active" | "stalled" | "resolved" | "shelved";

export interface PcLaneOwnedThread {
  id: string;
  title: string;
  status: string;
}

export interface PcLane {
  pc_id: number;
  slug: string;
  name: string;
  player: string | null;
  goal: string;
  status: PcLaneStatus;
  pressure: string;
  notes: string;
  last_touched_session: number | null;
  has_lane: boolean;
  owned_threads: PcLaneOwnedThread[];
}

export interface PcLaneUpsert {
  goal?: string;
  status?: PcLaneStatus;
  pressure?: string;
  notes?: string;
  last_touched_session?: number | null;
}
