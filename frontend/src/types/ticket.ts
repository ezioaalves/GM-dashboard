export interface Ticket {
  id: string;
  title: string;
  status: string;
  area: string;
  priority: "low" | "med" | "high";
  stage: string;
  parent_id: string | null;
  threads: string[];
  depends_on: string[];
  next_action: string;
  resume_note: string;
  body: string;
  introduced: string | null;
  closed: string | null;
  resolution: string;
  review_after: string | null;
}
