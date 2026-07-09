export interface CockpitTicket {
  id: string;
  title: string;
  status: string;
  stage: string;
  next_action: string;
  resume_note: string;
  review_after: string;
  area: string;
  priority: string;
  path: string;
  body_excerpt: string;
}

export interface CockpitLeaveOff {
  id: string;
  title: string;
  detail: string;
  source: string;
}

export interface CockpitSceneDeckItem {
  id: string;
  title: string;
  purpose: string;
  cast: string[];
  clock: string | null;
  foundry_needs: string[];
}

export interface CockpitCaptureItem {
  id: string;
  title: string;
  detail: string;
}

export interface CockpitLatestSession {
  session: number;
  title: string;
  date: string;
  path: string;
  body: string;
  summary: string;
  notable_moments: string[];
  npcs_present: string[];
  locations: string[];
  threads: Record<string, unknown>;
  has_secret: boolean;
}

export interface CockpitSession {
  latest_session: CockpitLatestSession;
  leave_off: CockpitLeaveOff;
  columns: {
    now: CockpitLeaveOff[];
    next: CockpitTicket[];
    scene_deck: CockpitSceneDeckItem[];
    capture: CockpitCaptureItem[];
    follow_up: CockpitTicket[];
  };
}

export interface FoundryStatus {
  state: "configured" | "unconfigured";
  path: string;
  detail?: string;
}
