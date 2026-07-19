import type { Severity } from "../components/Badge";
import type { PageKey } from "../navigation";
import { useSyncFreshnessQuery } from "../api/sync";
import { useRisksStaleQuery } from "../api/risks";
import { useFeedbackOverdueQuery } from "../api/feedback";
import { useCockpitThreadDirectionQuery } from "../api/cockpit";

export interface AttentionItem {
  key: string;
  severity: Severity;
  title: string;
  detail?: string;
  tags?: string[];
  actionLabel: string;
  targetPage: PageKey;
}

const SEVERITY_RANK: Record<Severity, number> = {
  conflict: 0,
  decision: 1,
  stale: 2,
  superseded: 3,
  fresh: 4,
};

/**
 * Merges the five "needs attention" endpoints (brief §8.4) into one ranked
 * list. Shared by the Cockpit feed and the sidebar's Cockpit badge count so
 * both agree on what counts as an item.
 */
export function useAttentionItems() {
  const { data: freshness } = useSyncFreshnessQuery();
  const { data: staleRisks = [] } = useRisksStaleQuery();
  const { data: overdueFeedback = [] } = useFeedbackOverdueQuery();
  const { data: threadDirection } = useCockpitThreadDirectionQuery();

  const items: AttentionItem[] = [];

  if (freshness) {
    for (const rev of freshness.items.filter((i) => i.kind === "review" && i.state === "conflict")) {
      items.push({
        key: `review-conflict-${rev.id}`,
        severity: "conflict",
        title: `Sync conflict — ${rev.review_type ?? "review"} on ${rev.target_id ?? rev.target_type}`,
        detail: "This review's source data has changed since it was proposed. Resolve in Sync Center.",
        actionLabel: "Resolve",
        targetPage: "sync-center",
      });
    }

    for (const job of freshness.items.filter((i) => i.kind === "job" && i.state === "failed")) {
      items.push({
        key: `job-failed-${job.id}`,
        severity: "conflict",
        title: `Sync job failed — ${job.job_type ?? "job"} on ${job.target ?? "target"}`,
        detail: job.error_message || job.error_code || "See Sync Center for details.",
        actionLabel: "Resolve",
        targetPage: "sync-center",
      });
    }

    const pendingReviews = freshness.items.filter((i) => i.kind === "review" && i.state === "pending");
    if (pendingReviews.length > 0) {
      items.push({
        key: "reviews-pending",
        severity: "decision",
        title: `${pendingReviews.length} sync review${pendingReviews.length === 1 ? "" : "s"} waiting`,
        tags: pendingReviews
          .slice(0, 4)
          .map((r) => `${(r.review_type ?? "review").toUpperCase()} · ${r.target_id ?? r.target_type}`),
        actionLabel: "Review",
        targetPage: "sync-center",
      });
    }

    for (const integ of freshness.items.filter((i) => i.kind === "integration")) {
      items.push({
        key: `integration-${integ.id}`,
        severity: "decision",
        title: integ.label ?? "Integration needs configuration",
        actionLabel: "Review",
        targetPage: "sync-center",
      });
    }

    for (const st of freshness.items.filter((i) => i.kind === "state")) {
      items.push({
        key: `state-${st.id}`,
        severity: "stale",
        title: st.label ?? `${st.target_type ?? "record"} drift detected`,
        actionLabel: "Rescan",
        targetPage: "sync-center",
      });
    }
  }

  for (const fb of overdueFeedback) {
    items.push({
      key: `feedback-${fb.cadence}`,
      severity: "decision",
      title: `Player feedback overdue — ${fb.cadence}`,
      detail: `${fb.sessions_since_last} session(s) since the last ${fb.cadence.replace("_", " ")}. Threshold is ${fb.threshold}.`,
      actionLabel: "Log now",
      targetPage: "feedback",
    });
  }

  if (staleRisks.length > 0) {
    items.push({
      key: "risks-stale",
      severity: "stale",
      title: `${staleRisks.length} risk${staleRisks.length === 1 ? "" : "s"} not reviewed recently`,
      detail: staleRisks
        .slice(0, 2)
        .map((r) => `"${r.title}" — likelihood: ${r.likelihood}`)
        .join(" · "),
      actionLabel: "Mark reviewed",
      targetPage: "risks",
    });
  }

  if (threadDirection) {
    for (const thread of threadDirection.stale_threads.filter((t) => t.stale_state.state !== "current")) {
      const needsDirection = thread.stale_state.state === "needs_direction";
      items.push({
        key: `thread-${thread.id}`,
        severity: "stale",
        title: needsDirection ? `Thread ${thread.id} has no next move` : `Thread ${thread.id} is stale`,
        detail: thread.stale_state.reasons.join(" · ") || undefined,
        actionLabel: "Open thread",
        targetPage: "threads",
      });
    }
  }

  items.sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
  return items;
}
