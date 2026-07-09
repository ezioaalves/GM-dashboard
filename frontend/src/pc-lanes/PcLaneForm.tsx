import { useState } from "react";
import { useUpsertPcLane } from "../api/pc-lanes";
import type { PcLane, PcLaneStatus } from "../types/pc-lane";

const STATUS_OPTIONS: PcLaneStatus[] = ["active", "stalled", "resolved", "shelved"];

export default function PcLaneForm({ lane, onDone }: { lane: PcLane; onDone: () => void }) {
  const [goal, setGoal] = useState(lane.goal);
  const [status, setStatus] = useState<PcLaneStatus>(lane.status);
  const [pressure, setPressure] = useState(lane.pressure);
  const [notes, setNotes] = useState(lane.notes);
  const [lastTouchedSession, setLastTouchedSession] = useState(
    lane.last_touched_session != null ? String(lane.last_touched_session) : ""
  );
  const upsert = useUpsertPcLane();

  async function save() {
    await upsert.mutateAsync({
      slug: lane.slug,
      goal,
      status,
      pressure,
      notes,
      last_touched_session: lastTouchedSession ? Number(lastTouchedSession) : null,
    });
    onDone();
  }

  return (
    <article className="card pc-lane-form">
      <h3>{lane.name}</h3>
      <label className="field">
        <span>Goal</span>
        <input value={goal} onChange={(e) => setGoal(e.target.value)} />
      </label>
      <label className="field">
        <span>Status</span>
        <select value={status} onChange={(e) => setStatus(e.target.value as PcLaneStatus)}>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Pressure</span>
        <input value={pressure} onChange={(e) => setPressure(e.target.value)} />
      </label>
      <label className="field">
        <span>Notes</span>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <label className="field">
        <span>Last touched session #</span>
        <input
          type="number"
          value={lastTouchedSession}
          onChange={(e) => setLastTouchedSession(e.target.value)}
        />
      </label>
      <div className="cardAction">
        <button onClick={save} disabled={upsert.isPending}>Save</button>
        <button onClick={onDone}>Cancel</button>
      </div>
    </article>
  );
}
