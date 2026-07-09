import { useState } from "react";
import { useDeleteRisk, useRisksQuery, useRisksStaleQuery } from "../api/risks";
import type { Risk } from "../types/risk";
import RiskForm from "./RiskForm";

function likelihoodBadgeClass(likelihood: string): string {
  return likelihood === "low" ? "ok" : likelihood === "medium" ? "warn" : "bad";
}

export default function RiskRegisterPanel() {
  const [statusFilter, setStatusFilter] = useState("");
  const [staleOnly, setStaleOnly] = useState(false);
  const { data: risks = [], isLoading, error } = useRisksQuery({ status: statusFilter || undefined });
  const { data: staleRisks = [] } = useRisksStaleQuery();
  const deleteRisk = useDeleteRisk();
  const [editing, setEditing] = useState<Risk | null | "new">(null);

  const staleIds = new Set(staleRisks.map((r) => r.id));
  const visibleRisks = staleOnly ? risks.filter((r) => staleIds.has(r.id)) : risks;

  if (editing !== null) {
    return <RiskForm risk={editing === "new" ? null : editing} onDone={() => setEditing(null)} />;
  }

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>Risk Register</h2>
          <p>Identify, rate, mitigate, and pre-build a contingency for load-bearing single points of failure.</p>
        </div>
        <button onClick={() => setEditing("new")}>New Risk</button>
      </div>

      <div className="risk-filters">
        <label className="field">
          <span>Status</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="mitigated">Mitigated</option>
            <option value="triggered">Triggered</option>
            <option value="closed">Closed</option>
          </select>
        </label>
        <label className="field">
          <span>
            <input type="checkbox" checked={staleOnly} onChange={(e) => setStaleOnly(e.target.checked)} />
            {" "}Not reviewed recently only
          </span>
        </label>
      </div>

      {isLoading && <p>Loading risks...</p>}
      {error && <p className="sync-error">{error.message}</p>}
      {!isLoading && visibleRisks.length === 0 && <p className="sync-empty">No risks match this view.</p>}

      <div className="results">
        {visibleRisks.map((risk) => (
          <article className="card" key={risk.id}>
            <h3>{risk.title || "Untitled risk"}</h3>
            <span className={`badge badge--${likelihoodBadgeClass(risk.likelihood)}`}>{risk.likelihood}</span>
            <span className="badge badge--ok">{risk.status}</span>
            {staleIds.has(risk.id) && <span className="badge badge--bad">not reviewed recently</span>}
            <p>{risk.description}</p>
            <div className="cardAction">
              <button onClick={() => setEditing(risk)}>Edit</button>
              <button onClick={() => deleteRisk.mutate(risk.id)}>Delete</button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
