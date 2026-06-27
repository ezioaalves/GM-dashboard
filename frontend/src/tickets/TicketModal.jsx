import React, { useState } from "react";
import { X } from "lucide-react";

const AREAS = ["lore", "mechanics", "foundry", "cosmetics", "skills", "docs", "housekeeping"];
const STAGES = ["now", "next", "deferred", "done"];
const STATUSES = ["open", "in_progress", "blocked", "done", "dropped"];
const PRIORITIES = ["high", "med", "low"];

export default function TicketModal({ ticket, defaultStage, onSave, onDelete, onClose }) {
  const isEdit = !!ticket.id;

  const [form, setForm] = useState({
    id: ticket.id || "",
    title: ticket.title || "",
    status: ticket.status || "open",
    area: ticket.area || "docs",
    priority: ticket.priority || "med",
    stage: ticket.stage || defaultStage || "next",
    parent_id: ticket.parent_id || "",
    threads: (ticket.threads || []).join(", "),
    depends_on: (ticket.depends_on || []).join(", "),
    next_action: ticket.next_action || "",
    resume_note: ticket.resume_note || "",
    resolution: ticket.resolution || "",
    body: ticket.body || "",
  });

  function field(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    const data = {
      ...form,
      threads: form.threads.split(",").map((s) => s.trim()).filter(Boolean),
      depends_on: form.depends_on.split(",").map((s) => s.trim()).filter(Boolean),
      parent_id: form.parent_id.trim() || null,
    };
    if (!isEdit) delete data.id; // let server generate if blank
    if (isEdit) data.id = ticket.id;
    onSave(data);
  }

  return (
    <div className="ticket-modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="ticket-modal">
        <div className="ticket-modal-header">
          <h2 className="ticket-modal-title">{isEdit ? "Edit Ticket" : "New Ticket"}</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#8fa8a0" }}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <label className="field span-all">
            <span>Title *</span>
            <input value={form.title} onChange={field("title")} required />
          </label>

          <div className="ticket-form-grid">
            <label className="field">
              <span>Stage</span>
              <select className="field-input" value={form.stage} onChange={field("stage")}>
                {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Status</span>
              <select className="field-input" value={form.status} onChange={field("status")}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Area</span>
              <select className="field-input" value={form.area} onChange={field("area")}>
                {AREAS.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Priority</span>
              <select className="field-input" value={form.priority} onChange={field("priority")}>
                {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
          </div>

          <label className="field">
            <span>Next action</span>
            <input value={form.next_action} onChange={field("next_action")} placeholder="Concrete next step to resume" />
          </label>

          <label className="field">
            <span>Resume note</span>
            <input value={form.resume_note} onChange={field("resume_note")} placeholder="Short context for returning to this" />
          </label>

          <label className="field">
            <span>Threads (comma-separated IDs)</span>
            <input value={form.threads} onChange={field("threads")} placeholder="shadowlands-escalation, onimusha-team-identity" />
          </label>

          <label className="field">
            <span>Depends on (comma-separated IDs)</span>
            <input value={form.depends_on} onChange={field("depends_on")} placeholder="some-other-ticket-id" />
          </label>

          <label className="field">
            <span>Parent ticket ID</span>
            <input value={form.parent_id} onChange={field("parent_id")} placeholder="parent-ticket-id" />
          </label>

          {form.status === "done" || form.status === "dropped" ? (
            <label className="field">
              <span>Resolution</span>
              <input value={form.resolution} onChange={field("resolution")} placeholder="One-line resolution summary" />
            </label>
          ) : null}

          <label className="field">
            <span>Body (Markdown)</span>
            <textarea
              value={form.body}
              onChange={field("body")}
              style={{ minHeight: 120 }}
              placeholder="Description, acceptance criteria, notes…"
            />
          </label>

          <div className="ticket-modal-footer">
            {isEdit ? (
              <button type="button" className="danger" onClick={() => onDelete(ticket.id)}>
                Delete
              </button>
            ) : <span />}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" onClick={onClose}>Cancel</button>
              <button type="submit">{isEdit ? "Save Changes" : "Create Ticket"}</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
