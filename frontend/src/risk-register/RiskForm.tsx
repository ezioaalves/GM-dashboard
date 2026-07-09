import { useState } from "react";
import { useCreateRisk, useMarkRiskReviewed, usePatchRisk } from "../api/risks";
import type { Risk, RiskLikelihood, RiskStatus } from "../types/risk";

const LIKELIHOOD_OPTIONS: RiskLikelihood[] = ["low", "medium", "high"];
const STATUS_OPTIONS: RiskStatus[] = ["open", "mitigated", "triggered", "closed"];

export default function RiskForm({ risk, onDone }: { risk: Risk | null; onDone: () => void }) {
  const [title, setTitle] = useState(risk?.title ?? "");
  const [description, setDescription] = useState(risk?.description ?? "");
  const [likelihood, setLikelihood] = useState<RiskLikelihood>(risk?.likelihood ?? "medium");
  const [mitigation, setMitigation] = useState(risk?.mitigation ?? "");
  const [contingency, setContingency] = useState(risk?.contingency ?? "");
  const [status, setStatus] = useState<RiskStatus>(risk?.status ?? "open");
  const [reviewSession, setReviewSession] = useState("");
  const create = useCreateRisk();
  const patch = usePatchRisk();
  const markReviewed = useMarkRiskReviewed();

  async function save() {
    const payload = { title, description, likelihood, mitigation, contingency, status };
    if (risk) {
      await patch.mutateAsync({ id: risk.id, ...payload });
    } else {
      await create.mutateAsync(payload);
    }
    onDone();
  }

  async function markAsReviewed() {
    if (!risk || !reviewSession) return;
    await markReviewed.mutateAsync({ id: risk.id, session_number: Number(reviewSession) });
  }

  return (
    <article className="card risk-form">
      <h3>{risk ? "Edit Risk" : "New Risk"}</h3>
      <label className="field">
        <span>Title (Identify)</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="field">
        <span>Description</span>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label className="field">
        <span>Likelihood (Rate)</span>
        <select value={likelihood} onChange={(e) => setLikelihood(e.target.value as RiskLikelihood)}>
          {LIKELIHOOD_OPTIONS.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Mitigation</span>
        <textarea value={mitigation} onChange={(e) => setMitigation(e.target.value)} />
      </label>
      <label className="field">
        <span>Contingency</span>
        <textarea value={contingency} onChange={(e) => setContingency(e.target.value)} />
      </label>
      <label className="field">
        <span>Status</span>
        <select value={status} onChange={(e) => setStatus(e.target.value as RiskStatus)}>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <div className="cardAction">
        <button onClick={save} disabled={create.isPending || patch.isPending}>Save</button>
        <button onClick={onDone}>Cancel</button>
      </div>

      {risk && (
        <div className="risk-review-action">
          <label className="field">
            <span>Mark reviewed at session #</span>
            <input
              type="number"
              value={reviewSession}
              onChange={(e) => setReviewSession(e.target.value)}
            />
          </label>
          <button onClick={markAsReviewed} disabled={!reviewSession || markReviewed.isPending}>
            Mark Reviewed
          </button>
          {risk.last_reviewed_session != null && (
            <p>Last reviewed at session {risk.last_reviewed_session}.</p>
          )}
        </div>
      )}
    </article>
  );
}
