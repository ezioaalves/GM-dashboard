import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useFeedbackOverdueQuery, useFeedbackQuery } from "../api/feedback";
import ActionItemsTable from "./ActionItemsTable";
import FeedbackEntryForm from "./FeedbackEntryForm";

const CADENCE_LABELS: Record<string, string> = {
  quick_check: "Quick check",
  arc_review: "Arc review",
  private_checkin: "Private check-in",
};

export default function FeedbackTrackerPanel() {
  const { data: entries = [], isLoading, error } = useFeedbackQuery();
  const { data: overdue = [] } = useFeedbackOverdueQuery();
  const [showForm, setShowForm] = useState(false);

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>Feedback Tracker</h2>
          <p>More of / less of / clarify, plus tracked action items.</p>
        </div>
        <button onClick={() => setShowForm(true)}>New Snapshot</button>
      </div>

      {overdue.length > 0 && (
        <section className="sync-freshness-alerts">
          {overdue.map((row) => (
            <div key={row.cadence} className="badge badge--bad">
              <AlertTriangle size={14} /> {CADENCE_LABELS[row.cadence] ?? row.cadence} overdue
              ({row.sessions_since_last} sessions since last)
            </div>
          ))}
        </section>
      )}

      {showForm && <FeedbackEntryForm onDone={() => setShowForm(false)} />}

      {isLoading && <p>Loading feedback...</p>}
      {error && <p className="sync-error">{error.message}</p>}
      {!isLoading && entries.length === 0 && <p className="sync-empty">No feedback recorded yet.</p>}

      <div className="results">
        {entries.map((entry) => (
          <article className="card" key={entry.id}>
            <h3>
              {CADENCE_LABELS[entry.cadence] ?? entry.cadence}
              {entry.session_number != null ? ` — Session ${entry.session_number}` : ""}
            </h3>
            {entry.players_present && <p><strong>Present:</strong> {entry.players_present}</p>}
            {entry.more_of && <p><strong>More Of:</strong> {entry.more_of}</p>}
            {entry.less_of && <p><strong>Less Of:</strong> {entry.less_of}</p>}
            {entry.clarify && <p><strong>Clarify:</strong> {entry.clarify}</p>}
            <ActionItemsTable entryId={entry.id} items={entry.action_items} />
          </article>
        ))}
      </div>
    </div>
  );
}
