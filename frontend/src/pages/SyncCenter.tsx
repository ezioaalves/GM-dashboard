import { useRef, useState } from "react";
import { Modal, Field } from "../components/Modal";
import {
  useSyncReviewsQuery,
  useSyncReviewDetailQuery,
  useDecideSyncReview,
  useApplySyncReview,
  useScanVault,
  useBulkApplySyncReviews,
} from "../api/sync";
import type { SyncReview } from "../types/sync";

type Filter = "all" | "conflict" | "pending" | "stale" | "decided";

const STATUS_META: Record<string, { label: string; cls: string }> = {
  conflict: { label: "CONFLICT", cls: "conflict" },
  pending: { label: "PENDING", cls: "decision" },
  stale: { label: "STALE", cls: "superseded" },
  accepted: { label: "ACCEPTED", cls: "superseded" },
  merged: { label: "MERGED", cls: "superseded" },
  rejected: { label: "REJECTED", cls: "superseded" },
  deferred: { label: "DEFERRED", cls: "superseded" },
};

function reviewTitle(review: SyncReview): string {
  return `${review.target_type}: ${review.target_id}`;
}

/** Render a proposed-changes payload as field → value diff rows, generically. */
function diffRows(payload: Record<string, unknown> | undefined): Array<{ field: string; from: string; to: string }> {
  if (!payload) return [];
  const rows: Array<{ field: string; from: string; to: string }> = [];
  const diff = payload.diff;
  if (diff && typeof diff === "object" && !Array.isArray(diff)) {
    for (const [field, v] of Object.entries(diff as Record<string, unknown>)) {
      if (v && typeof v === "object" && ("from" in (v as object) || "to" in (v as object))) {
        const vv = v as { from?: unknown; to?: unknown };
        rows.push({ field, from: JSON.stringify(vv.from ?? "—"), to: JSON.stringify(vv.to ?? "—") });
      } else {
        rows.push({ field, from: "—", to: JSON.stringify(v) });
      }
    }
    return rows;
  }
  for (const [field, v] of Object.entries(payload)) {
    const to = typeof v === "string" ? v : JSON.stringify(v);
    rows.push({ field, from: "—", to: to.length > 140 ? `${to.slice(0, 140)}…` : to });
  }
  return rows;
}

function ReviewCard({
  review,
  onError,
}: {
  review: SyncReview;
  onError: (msg: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [mergeDraft, setMergeDraft] = useState("");
  const { data: detail } = useSyncReviewDetailQuery(expanded || mergeOpen ? review.id : null);
  const decide = useDecideSyncReview();
  const apply = useApplySyncReview();

  const status = review.review_status;
  const meta = STATUS_META[status] ?? STATUS_META.pending;
  const dimmed = ["stale", "rejected", "deferred"].includes(status);
  const showDecision = status === "pending";
  const showConflict = status === "conflict";
  const showApply = (status === "accepted" || status === "merged") && !review.applied_at;
  const rows = diffRows(detail?.proposed_changes);

  return (
    <div className={`review-card${status === "conflict" ? " review-card--conflict" : ""}${dimmed ? " review-card--dim" : ""}`}>
      <div className="review-card-header" onClick={() => setExpanded(!expanded)}>
        <span className="review-type-badge">{review.review_type.toUpperCase()}</span>
        <span className="review-card-title">{reviewTitle(review)}</span>
        <span className={`badge-pill badge-pill--${meta.cls}`} style={{ marginLeft: "auto" }}>
          <span className="badge-pill-dot" />
          {meta.label}
        </span>
      </div>

      {expanded && (
        <div className="review-diff">
          {rows.length === 0 && <span className="drawer-empty">No structured payload on this review.</span>}
          {rows.map((row, i) => (
            <div className="review-diff-row" key={i}>
              <span className="review-diff-field">{row.field}</span>
              {row.from !== "—" && <span className="review-diff-from">{row.from}</span>}
              {row.from !== "—" && <span style={{ color: "var(--text-faint)" }}>→</span>}
              <span className="review-diff-to">{row.to}</span>
            </div>
          ))}
          {detail?.proposed_changes && (
            <details className="review-raw">
              <summary>raw payload</summary>
              <pre>{JSON.stringify(detail.proposed_changes, null, 2)}</pre>
            </details>
          )}
        </div>
      )}

      {status === "stale" && (
        <div className="review-note review-note--muted">
          Outdated, not rejected — a re-import replaced this proposal before you decided on it.
        </div>
      )}

      {apply.isError && (
        <div className="review-note">⚑ {apply.error.message}</div>
      )}

      {showDecision && (
        <div className="review-actions">
          <button
            className="btn btn-primary"
            disabled={decide.isPending}
            onClick={() => decide.mutate({ id: review.id, review_status: "accepted" })}
          >
            Accept
          </button>
          <button
            className="btn-ghost"
            onClick={() => {
              setMergeDraft("");
              setMergeOpen(true);
            }}
          >
            Merge…
          </button>
          <button
            className="btn-ghost"
            disabled={decide.isPending}
            onClick={() => decide.mutate({ id: review.id, review_status: "deferred" })}
          >
            Defer
          </button>
          <button
            className="btn-danger-ghost"
            disabled={decide.isPending}
            onClick={() => decide.mutate({ id: review.id, review_status: "rejected" })}
          >
            Reject
          </button>
          <span className="board-hint" style={{ marginLeft: "auto" }}>
            Apply is a separate confirm step
          </span>
        </div>
      )}

      {showConflict && (
        <div className="review-actions">
          <button
            className="btn btn-primary"
            disabled={decide.isPending || apply.isPending}
            onClick={() =>
              decide.mutate(
                { id: review.id, review_status: "accepted" },
                {
                  onSuccess: () =>
                    apply.mutate(review.id, { onError: (err) => onError(err.message) }),
                },
              )
            }
          >
            Adopt proposed value
          </button>
          <button
            className="btn-ghost"
            disabled={decide.isPending}
            onClick={() => decide.mutate({ id: review.id, review_status: "rejected" })}
          >
            Keep local
          </button>
          <span className="board-hint" style={{ marginLeft: "auto" }}>
            conflict flags: {review.conflict_flags.join(", ") || "—"}
          </span>
        </div>
      )}

      {showApply && (
        <div className="review-actions">
          <button
            className="btn-block"
            style={{ flex: "none", padding: "7px 16px" }}
            disabled={apply.isPending}
            onClick={() => apply.mutate(review.id, { onError: (err) => onError(err.message) })}
          >
            {apply.isPending ? "Applying…" : "Apply"}
          </button>
          <span className="board-hint" style={{ marginLeft: "auto" }}>
            Idempotent — safe to click once, safe to double-click
          </span>
        </div>
      )}

      {review.applied_at && (
        <div className="review-actions">
          <span className="badge-pill badge-pill--fresh">
            <span className="badge-pill-dot" />
            APPLIED
          </span>
          <span className="board-hint" style={{ marginLeft: "auto" }}>
            applied {new Date(review.applied_at).toLocaleString()}
          </span>
        </div>
      )}

      {mergeOpen && (
        <Modal
          title={`Merge — ${reviewTitle(review)}`}
          onClose={() => setMergeOpen(false)}
          footer={
            <>
              <button className="btn-ghost" onClick={() => setMergeOpen(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={decide.isPending}
                onClick={() => {
                  let decision: Record<string, unknown> = { merged_note: mergeDraft };
                  try {
                    decision = { merged: JSON.parse(mergeDraft) };
                  } catch {
                    /* keep free-text note */
                  }
                  decide.mutate(
                    { id: review.id, review_status: "merged", decision },
                    { onSuccess: () => setMergeOpen(false) },
                  );
                }}
              >
                Save merged value &amp; accept
              </button>
            </>
          }
        >
          <span className="panel-note">
            Edit the merged value before accepting. Adjust the resolved payload directly — it is
            stored on the review as your decision.
          </span>
          <Field label="MERGED VALUE">
            <textarea
              className="textarea"
              style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, minHeight: 160 }}
              value={mergeDraft || JSON.stringify(detail?.proposed_changes ?? {}, null, 2)}
              onChange={(e) => setMergeDraft(e.target.value)}
            />
          </Field>
        </Modal>
      )}
    </div>
  );
}

export function SyncCenter() {
  const { data: reviews = [] } = useSyncReviewsQuery();
  const scan = useScanVault();
  const bulkApply = useBulkApplySyncReviews();
  const [filter, setFilter] = useState<Filter>("all");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4200);
  }

  const counts = {
    all: reviews.length,
    conflict: reviews.filter((r) => r.review_status === "conflict").length,
    pending: reviews.filter((r) => r.review_status === "pending").length,
    stale: reviews.filter((r) => r.review_status === "stale").length,
    decided: reviews.filter(
      (r) => ["accepted", "merged"].includes(r.review_status) && !r.applied_at,
    ).length,
  };

  const visible = reviews.filter((r) => {
    if (filter === "all") return true;
    if (filter === "decided")
      return ["accepted", "merged"].includes(r.review_status) && !r.applied_at;
    return r.review_status === filter;
  });

  const filters: Array<{ key: Filter; label: string; dot?: string }> = [
    { key: "all", label: "All" },
    { key: "conflict", label: "Conflict", dot: "var(--red-bright)" },
    { key: "pending", label: "Pending", dot: "var(--amber-bright)" },
    { key: "stale", label: "Stale", dot: "var(--azure)" },
    { key: "decided", label: "Accepted, not yet applied", dot: "var(--text-faint)" },
  ];

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Sync Center</h1>
          <span className="page-subtitle">
            unified review inbox — reviews, jobs, and freshness alerts
          </span>
        </div>
        <div className="header-actions">
          <button
            className="btn-ghost"
            disabled={bulkApply.isPending || counts.pending + counts.decided === 0}
            onClick={() => {
              const outstanding = counts.pending + counts.decided;
              if (!window.confirm(`Accept and apply ${outstanding} outstanding review(s)?`)) return;
              bulkApply.mutate(undefined, {
                onSuccess: (result) => {
                  const summary = result.failed.length
                    ? `${result.applied.length} applied, ${result.failed.length} need attention`
                    : `${result.applied.length} applied`;
                  showToast(summary);
                },
                onError: (err) => showToast(`Bulk apply failed: ${err.message}`),
              });
            }}
          >
            {bulkApply.isPending ? "Applying…" : "Accept all"}
          </button>
          <button
            className="btn-ghost"
            disabled={scan.isPending}
            onClick={() =>
              scan.mutate(undefined, {
                onSuccess: () => showToast("Vault scan finished — new proposals appear below"),
                onError: (err) => showToast(`Scan failed: ${err.message}`),
              })
            }
          >
            {scan.isPending ? "Scanning…" : "Scan vault"}
          </button>
        </div>
      </header>

      <div className="filter-strip">
        {filters.map((f) => (
          <button
            key={f.key}
            className={`filter-pill${filter === f.key ? " filter-pill--active" : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.dot && <span className="filter-dot" style={{ background: f.dot }} />}
            {f.label} <span style={{ opacity: 0.6 }}>{counts[f.key]}</span>
          </button>
        ))}
      </div>

      <div className="review-list">
        {visible.length === 0 && (
          <div className="empty-state">Nothing here — inbox is clear for this filter.</div>
        )}
        {visible.map((review) => (
          <ReviewCard key={review.id} review={review} onError={showToast} />
        ))}
      </div>

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
