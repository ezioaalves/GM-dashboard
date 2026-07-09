import { useState } from "react";
import { useCreateFeedbackEntry } from "../api/feedback";
import type { FeedbackCadence } from "../types/feedback";

const CADENCE_OPTIONS: FeedbackCadence[] = ["quick_check", "arc_review", "private_checkin"];

export default function FeedbackEntryForm({ onDone }: { onDone: () => void }) {
  const [sessionNumber, setSessionNumber] = useState("");
  const [cadence, setCadence] = useState<FeedbackCadence>("quick_check");
  const [playersPresent, setPlayersPresent] = useState("");
  const [moreOf, setMoreOf] = useState("");
  const [lessOf, setLessOf] = useState("");
  const [clarify, setClarify] = useState("");
  const [notes, setNotes] = useState("");
  const create = useCreateFeedbackEntry();

  async function save() {
    await create.mutateAsync({
      session_number: sessionNumber ? Number(sessionNumber) : null,
      cadence,
      players_present: playersPresent,
      more_of: moreOf,
      less_of: lessOf,
      clarify,
      notes,
    });
    onDone();
  }

  return (
    <article className="card feedback-entry-form">
      <h3>New Feedback Snapshot</h3>
      <label className="field">
        <span>Session #</span>
        <input type="number" value={sessionNumber} onChange={(e) => setSessionNumber(e.target.value)} />
      </label>
      <label className="field">
        <span>Cadence</span>
        <select value={cadence} onChange={(e) => setCadence(e.target.value as FeedbackCadence)}>
          {CADENCE_OPTIONS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Players present</span>
        <input value={playersPresent} onChange={(e) => setPlayersPresent(e.target.value)} />
      </label>
      <label className="field">
        <span>More Of</span>
        <textarea value={moreOf} onChange={(e) => setMoreOf(e.target.value)} />
      </label>
      <label className="field">
        <span>Less Of</span>
        <textarea value={lessOf} onChange={(e) => setLessOf(e.target.value)} />
      </label>
      <label className="field">
        <span>Clarify</span>
        <textarea value={clarify} onChange={(e) => setClarify(e.target.value)} />
      </label>
      <label className="field">
        <span>Notes</span>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <div className="cardAction">
        <button onClick={save} disabled={create.isPending}>Save</button>
        <button onClick={onDone}>Cancel</button>
      </div>
    </article>
  );
}
