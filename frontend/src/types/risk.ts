export type RiskLikelihood = "low" | "medium" | "high";
export type RiskStatus = "open" | "mitigated" | "triggered" | "closed";

export interface Risk {
  id: number;
  title: string;
  description: string;
  likelihood: RiskLikelihood;
  mitigation: string;
  contingency: string;
  status: RiskStatus;
  related_thread_id: string | null;
  related_pc_id: number | null;
  last_reviewed_session: number | null;
}

export interface RiskCreate {
  title?: string;
  description?: string;
  likelihood?: RiskLikelihood;
  mitigation?: string;
  contingency?: string;
  status?: RiskStatus;
  related_thread_id?: string | null;
  related_pc_id?: number | null;
}

export type RiskPatch = Partial<RiskCreate>;
