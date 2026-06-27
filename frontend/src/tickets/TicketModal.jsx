import React, { useState, useEffect } from "react";
import { X } from "lucide-react";
import CustomSelect from "../components/CustomSelect.jsx";
import MultiTagSelect from "../components/MultiTagSelect.jsx";

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
    parent_id: ticket.parent_id || null,
    threads: ticket.threads || [],
    depends_on: ticket.depends_on || [],
    next_action: ticket.next_action || "",
    resume_note: ticket.resume_note || "",
    resolution: ticket.resolution || "",
    body: ticket.body || "",
  });

  const [threadOptions, setThreadOptions] = useState([]);
  const [ticketOptions, setTicketOptions] = useState([]);

  useEffect(() => {
    fetch("/api/threads")
      .then((r) => r.json())
      .then((data) => setThreadOptions(data.map((t) => ({ value: t.id, label: t.title || t.id }))))
      .catch(() => {});
    fetch("/api/tickets")
      .then((r) => r.json())
      .then((data) =>
        setTicketOptions(
          data
            .filter((t) => t.id !== ticket.id)
            .map((t) => ({ value: t.id, label: t.title || t.id }))
        )
      )
      .catch(() => {});
  }, [ticket.id]);

  function field(key) {
    return (val) => setForm((f) => ({ ...f, [key]: val }));
  }

  function fieldEvent(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    const data = {
      ...form,
      parent_id: form.parent_id || null,
    };
    if (!isEdit) delete data.id;
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
            <input value={form.title} onChange={fieldEvent("title")} required />
          </label>

          <div className="ticket-form-grid">
            <label className="field">
              <span>Stage</span>
              <CustomSelect value={form.stage} onChange={field("stage")} options={STAGES} />
            </label>
            <label className="field">
              <span>Status</span>
              <CustomSelect value={form.status} onChange={field("status")} options={STATUSES} />
            </label>
            <label className="field">
              <span>Area</span>
              <CustomSelect value={form.area} onChange={field("area")} options={AREAS} />
            </label>
            <label className="field">
              <span>Priority</span>
              <CustomSelect value={form.priority} onChange={field("priority")} options={PRIORITIES} />
            </label>
          </div>

          <label className="field">
            <span>Next action</span>
            <input value={form.next_action} onChange={fieldEvent("next_action")} placeholder="Concrete next step to resume" />
          </label>

          <label className="field">
            <span>Resume note</span>
            <input value={form.resume_note} onChange={fieldEvent("resume_note")} placeholder="Short context for returning to this" />
          </label>

          <label className="field">
            <span>Threads</span>
            <MultiTagSelect
              values={form.threads}
              onChange={field("threads")}
              options={threadOptions}
              placeholder="Search threads…"
            />
          </label>

          <label className="field">
            <span>Depends on</span>
            <MultiTagSelect
              values={form.depends_on}
              onChange={field("depends_on")}
              options={ticketOptions}
              placeholder="Search tickets…"
            />
          </label>

          <label className="field">
            <span>Parent ticket</span>
            <CustomSelect
              value={form.parent_id || ""}
              onChange={(v) => setForm((f) => ({ ...f, parent_id: v || null }))}
              options={[{ value: "", label: "— none —" }, ...ticketOptions]}
              placeholder="— none —"
            />
          </label>

          {form.status === "done" || form.status === "dropped" ? (
            <label className="field">
              <span>Resolution</span>
              <input value={form.resolution} onChange={fieldEvent("resolution")} placeholder="One-line resolution summary" />
            </label>
          ) : null}

          <label className="field">
            <span>Body (Markdown)</span>
            <textarea
              value={form.body}
              onChange={fieldEvent("body")}
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
