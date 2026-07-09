import type { ReactNode } from "react";

export type Severity = "conflict" | "decision" | "stale" | "superseded" | "fresh";

const LABELS: Record<Severity, string> = {
  conflict: "CONFLICT",
  decision: "DECISION",
  stale: "STALE",
  superseded: "SUPERSEDED",
  fresh: "FRESH",
};

export function SeverityBadge({ severity, label }: { severity: Severity; label?: string }) {
  return (
    <span className={`badge-pill badge-pill--${severity}`}>
      <span className="badge-pill-dot" />
      {label ?? LABELS[severity]}
    </span>
  );
}

export function TagPill({ children }: { children: ReactNode }) {
  return <span className="tag-pill">{children}</span>;
}
