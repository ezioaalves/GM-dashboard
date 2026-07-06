import { useState } from "react";
import { AlertTriangle, Check, RefreshCw, X } from "lucide-react";
import { useApplySyncReview, useDecideSyncReview, useGroupedSyncReviewsQuery } from "../api/sync";
import type { SyncReview } from "../types/sync";

const TARGET_TYPE_LABELS: Record<string, string> = {
  ticket: "Tickets",
  thread: "Threads",
  npc: "NPCs",
  clock: "Clocks",
  relationship: "Relationships",
  asset: "Assets",
  entity: "Lore Entities",
};

function canApply(review: SyncReview): boolean {
  return review.review_status === "accepted" || review.review_status === "merged";
}

export default function SyncCenter() {
  const { data, isLoading, error, refetch } = useGroupedSyncReviewsQuery();
  const decide = useDecideSyncReview();
  const apply = useApplySyncReview();
  const [actionError, setActionError] = useState("");

  async function handleDecide(review: SyncReview, review_status: string) {
    setActionError("");
    try {
      await decide.mutateAsync({ id: review.id, review_status });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleApply(review: SyncReview) {
    setActionError("");
    try {
      await apply.mutateAsync(review.id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  const groups = data?.groups ?? [];

  return (
    <div className="toolPanel sync-center">
      <div className="panelHeader">
        <div>
          <h2>Sync Center</h2>
          <p>Pending reviews grouped by what they affect. Decide, then apply.</p>
        </div>
        <button onClick={() => refetch()}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {actionError && (
        <div className="sync-error">
          <AlertTriangle size={16} /> {actionError}
        </div>
      )}

      {isLoading && <p>Loading reviews...</p>}
      {error && <p className="sync-error">{error.message}</p>}

      {!isLoading && groups.length === 0 && (
        <p className="sync-empty">Nothing pending. Sync is fresh.</p>
      )}

      {groups.map((group) => (
        <section className="sync-group" key={group.target_type}>
          <h3>
            {TARGET_TYPE_LABELS[group.target_type] ?? group.target_type}
            <span className="sync-group-count">{group.count}</span>
          </h3>
          <div className="sync-review-list">
            {group.reviews.map((review) => (
              <article className="sync-review-card" key={review.id}>
                <div className="sync-review-header">
                  <span className="sync-review-type">{review.review_type}</span>
                  <span className={`badge badge--${review.review_status === "conflict" ? "bad" : "warn"}`}>
                    {review.review_status}
                  </span>
                </div>
                <div className="sync-review-surfaces">
                  {review.source_surface} &rarr; {review.target_surface}
                </div>
                {review.conflict_flags.length > 0 && (
                  <div className="sync-review-conflicts">
                    <AlertTriangle size={14} /> {review.conflict_flags.join(", ")}
                  </div>
                )}
                <div className="sync-review-actions">
                  <button onClick={() => handleDecide(review, "accepted")} disabled={decide.isPending}>
                    <Check size={14} /> Accept
                  </button>
                  <button onClick={() => handleDecide(review, "rejected")} disabled={decide.isPending}>
                    <X size={14} /> Reject
                  </button>
                  <button onClick={() => handleDecide(review, "deferred")} disabled={decide.isPending}>
                    Defer
                  </button>
                  {canApply(review) && (
                    <button className="sync-apply-button" onClick={() => handleApply(review)} disabled={apply.isPending}>
                      Apply
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
