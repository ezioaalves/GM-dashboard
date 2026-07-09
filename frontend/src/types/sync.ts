export interface SyncReview {
  id: string;
  review_type: string;
  source_surface: string;
  target_surface: string;
  target_type: string;
  target_id: string;
  base_version: string;
  current_version: string;
  conflict_flags: string[];
  review_status: "pending" | "accepted" | "rejected" | "merged" | "deferred" | "conflict" | "stale";
  created_at: string;
  updated_at: string;
  decided_at: string | null;
  applied_at: string | null;
}

export interface SyncReviewGroup {
  target_type: string;
  count: number;
  reviews: SyncReview[];
}

export interface SyncFreshnessItem {
  kind: "review" | "job" | "state" | "integration";
  id: string;
  state: string;
  priority: "high" | "normal";
  updated_at: string | null;
  review_type?: string;
  target_type?: string;
  target_id?: string;
  job_type?: string;
  target?: string;
  error_code?: string;
  error_message?: string;
  label?: string;
}

export interface SyncFreshness {
  state: "fresh" | "pending" | "stale" | "conflict" | "failed";
  counts: {
    pending_reviews: number;
    conflict_reviews: number;
    stale_reviews: number;
    failed_jobs: number;
    blocked_jobs: number;
    stale_records: number;
    stale_vault: number;
    stale_asset: number;
    stale_foundry: number;
    unconfigured_integrations: number;
  };
  items: SyncFreshnessItem[];
}
