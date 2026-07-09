import { useState } from "react";
import { usePcLanesQuery } from "../api/pc-lanes";
import PcLaneForm from "./PcLaneForm";

function statusBadgeClass(status: string): string {
  return status === "active" ? "ok" : status === "resolved" ? "ok" : status === "stalled" ? "warn" : "bad";
}

export default function PcLanesPanel() {
  const { data: lanes = [], isLoading, error } = usePcLanesQuery();
  const [editingSlug, setEditingSlug] = useState<string | null>(null);

  const editing = lanes.find((l) => l.slug === editingSlug) ?? null;

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>PC Lanes</h2>
          <p>Per-PC goal, status, and pressure — owned threads are shown read-only, not duplicated here.</p>
        </div>
      </div>

      {isLoading && <p>Loading PC lanes...</p>}
      {error && <p className="sync-error">{error.message}</p>}

      {editing && <PcLaneForm lane={editing} onDone={() => setEditingSlug(null)} />}

      {!editing && (
        <div className="results">
          {lanes.map((lane) => (
            <article className="card" key={lane.pc_id}>
              <h3>{lane.name}</h3>
              <span className={`badge badge--${statusBadgeClass(lane.status)}`}>{lane.status}</span>
              <p>{lane.goal || "No goal set yet."}</p>
              {lane.pressure && <p><strong>Pressure:</strong> {lane.pressure}</p>}
              {lane.owned_threads.length > 0 && (
                <div className="pc-lane-threads">
                  <strong>Owned threads:</strong>
                  <ul>
                    {lane.owned_threads.map((t) => (
                      <li key={t.id}>{t.title} <span className="badge badge--ok">{t.status}</span></li>
                    ))}
                  </ul>
                </div>
              )}
              <button className="cardAction" onClick={() => setEditingSlug(lane.slug)}>
                {lane.has_lane ? "Edit lane" : "Set up lane"}
              </button>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
