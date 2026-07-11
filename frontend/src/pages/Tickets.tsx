import { useEffect, useRef, useState } from "react";
import {
  DndContext,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { Modal, Field } from "../components/Modal";
import { PillSelect } from "../components/PillSelect";
import type { PageKey } from "../components/Sidebar";
import {
  useTicketsQuery,
  useCreateTicket,
  useUpdateTicket,
  usePatchTicketStage,
  useDeleteTicket,
  useImportTicketsFromVault,
} from "../api/tickets";
import type { Ticket } from "../types/ticket";

const STAGES = ["now", "next", "deferred", "done"] as const;
const STATUSES = ["open", "in_progress", "blocked", "done", "dropped"] as const;
const AREAS = ["lore", "mechanics", "foundry", "cosmetics", "skills", "docs", "housekeeping"] as const;
const PRIORITIES = ["high", "med", "low"] as const;

function ticketPutPayload(t: Ticket) {
  return {
    title: t.title,
    status: t.status,
    area: t.area,
    priority: t.priority,
    stage: t.stage,
    parent_id: t.parent_id,
    threads: t.threads,
    depends_on: t.depends_on,
    next_action: t.next_action,
    resume_note: t.resume_note,
    resolution: t.resolution,
    body: t.body,
  };
}

function TicketCard({ ticket, childCount, onOpen }: { ticket: Ticket; childCount: number; onOpen: () => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: ticket.id,
  });
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 5 }
    : undefined;
  const hasMeta = ticket.depends_on.length > 0 || childCount > 0 || ticket.parent_id != null;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`deck-card${isDragging ? " scene-card--dragging" : ""}`}
      onClick={onOpen}
      {...listeners}
      {...attributes}
    >
      <span className="deck-card-title" style={{ fontSize: 13.5 }}>
        {ticket.title}
      </span>
      <div className="deck-card-badges">
        <span className="tag-pill">{ticket.area}</span>
        <span className={`priority-chip priority-chip--${ticket.priority}`}>{ticket.priority}</span>
        <span className={`ticket-status-chip ticket-status-chip--${ticket.status}`}>
          {ticket.status.replace("_", " ")}
        </span>
      </div>
      {hasMeta && (
        <div className="deck-card-meta">
          {ticket.depends_on.length > 0 && <span>⛓ {ticket.depends_on.length} deps</span>}
          {childCount > 0 && <span>└ {childCount} subtickets</span>}
          {ticket.parent_id != null && <span>↑ has parent</span>}
        </div>
      )}
    </div>
  );
}

function TicketLane({
  stage,
  tickets,
  allTickets,
  onOpen,
}: {
  stage: (typeof STAGES)[number];
  tickets: Ticket[];
  allTickets: Ticket[];
  onOpen: (t: Ticket) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <div ref={setNodeRef} className={`deck-lane${isOver ? " lane--over" : ""}`} style={{ minHeight: 260 }}>
      <div className="deck-lane-header">
        <span className={`column-heading-label stage-label--${stage}`}>{stage.toUpperCase()}</span>
        <span className="lane-count">{tickets.length}</span>
      </div>
      <div className="deck-lane-cards" style={{ minHeight: 60 }}>
        {tickets.map((t) => (
          <TicketCard
            key={t.id}
            ticket={t}
            childCount={allTickets.filter((c) => c.parent_id === t.id).length}
            onOpen={() => onOpen(t)}
          />
        ))}
        {tickets.length === 0 && <div className="deck-lane-empty">drop a ticket here</div>}
      </div>
    </div>
  );
}

function TicketDrawer({
  ticket,
  allTickets,
  onClose,
  onOpenTicket,
  toast,
}: {
  ticket: Ticket;
  allTickets: Ticket[];
  onClose: () => void;
  onOpenTicket: (id: string) => void;
  toast: (msg: string) => void;
}) {
  const updateTicket = useUpdateTicket();
  const deleteTicket = useDeleteTicket();

  const [local, setLocal] = useState<Ticket>(ticket);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [depDraft, setDepDraft] = useState("");
  const [threadDraft, setThreadDraft] = useState("");
  const dirty = useRef(false);

  useEffect(() => {
    setLocal(ticket);
    dirty.current = false;
    setConfirmingDelete(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticket.id]);

  useEffect(() => {
    if (!dirty.current) return;
    const t = setTimeout(() => {
      updateTicket.mutate({ id: local.id, ...ticketPutPayload(local) });
      dirty.current = false;
    }, 800);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);

  function update(patch: Partial<Ticket>) {
    dirty.current = true;
    setLocal((prev) => ({ ...prev, ...patch }));
  }

  const parent = allTickets.find((t) => t.id === local.parent_id) ?? null;
  const children = allTickets.filter((t) => t.parent_id === local.id);

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer drawer--wide" style={{ width: 560 }}>
        <div className="editor-drawer-header">
          <div className="editor-drawer-heading">
            <span className="editor-drawer-title">{local.title}</span>
            <span className="page-subtitle">
              #{local.id} · ticket detail · changes save as you type
            </span>
          </div>
          <button className="drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="editor-drawer-body">
          <Field label="TITLE">
            <input
              className="input"
              style={{ fontWeight: 600, fontSize: 14 }}
              value={local.title}
              onChange={(e) => update({ title: e.target.value })}
            />
          </Field>

          <div className="adventure-summary-grid" style={{ gap: 16 }}>
            <Field label="STAGE (kanban lane)">
              <PillSelect
                options={STAGES}
                value={local.stage as (typeof STAGES)[number]}
                onChange={(stage) => update({ stage })}
              />
            </Field>
            <Field label="PRIORITY">
              <PillSelect
                options={PRIORITIES}
                value={local.priority}
                onChange={(priority) => update({ priority })}
              />
            </Field>
            <Field label="STATUS">
              <PillSelect
                options={STATUSES}
                value={local.status as (typeof STATUSES)[number]}
                onChange={(status) => update({ status })}
                labels={{ in_progress: "in progress" }}
              />
            </Field>
            <Field label="AREA">
              <PillSelect
                options={AREAS}
                value={local.area as (typeof AREAS)[number]}
                onChange={(area) => update({ area })}
              />
            </Field>
          </div>

          <Field label="DESCRIPTION">
            <textarea
              className="textarea"
              style={{ minHeight: 72 }}
              value={local.body}
              onChange={(e) => update({ body: e.target.value })}
            />
          </Field>

          <Field label="NEXT ACTION" hint="the single next concrete step">
            <input
              className="input"
              value={local.next_action}
              onChange={(e) => update({ next_action: e.target.value })}
            />
          </Field>

          <Field label="RESUME NOTES" hint="where to pick this back up">
            <textarea
              className="textarea"
              style={{ minHeight: 56 }}
              value={local.resume_note}
              onChange={(e) => update({ resume_note: e.target.value })}
            />
          </Field>

          {(local.status === "done" || local.status === "dropped" || local.resolution) && (
            <Field label="RESOLUTION" hint="how this ticket ended">
              <textarea
                className="textarea"
                style={{ minHeight: 56 }}
                value={local.resolution}
                onChange={(e) => update({ resolution: e.target.value })}
              />
            </Field>
          )}

          <div className="drawer-section">
            <span className="drawer-section-label">HIERARCHY</span>
            {parent && (
              <button className="hierarchy-row" onClick={() => onOpenTicket(parent.id)}>
                <span className="child-key">PARENT ↑</span>
                <span>{parent.title}</span>
              </button>
            )}
            {children.map((c) => (
              <button className="hierarchy-row" key={c.id} onClick={() => onOpenTicket(c.id)}>
                <span className="child-key">CHILD └</span>
                <span>{c.title}</span>
                <span className={`stage-label--${c.stage} mono-inline`} style={{ marginLeft: "auto", fontSize: 10 }}>
                  {c.stage.toUpperCase()}
                </span>
              </button>
            ))}
            {!parent && children.length === 0 && (
              <span className="drawer-empty">No parent or subtickets.</span>
            )}
          </div>

          <div className="adventure-summary-grid" style={{ gap: 16 }}>
            <div className="drawer-section" style={{ borderTop: "none", paddingTop: 0 }}>
              <span className="drawer-section-label">DEPENDS ON</span>
              <div className="pin-chip-row">
                {local.depends_on.map((dp, i) => (
                  <span className="dep-chip" key={i}>
                    {dp}
                    <button
                      className="editor-clue-remove"
                      onClick={() => update({ depends_on: local.depends_on.filter((_, j) => j !== i) })}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
              <div className="editor-clue-add">
                <input
                  className="input"
                  style={{ flex: 1, width: "auto", minWidth: 0 }}
                  placeholder="Add dependency…"
                  value={depDraft}
                  onChange={(e) => setDepDraft(e.target.value)}
                />
                <button
                  className="board-new-scene"
                  style={{ marginLeft: 0 }}
                  onClick={() => {
                    if (!depDraft.trim()) return;
                    update({ depends_on: [...local.depends_on, depDraft.trim()] });
                    setDepDraft("");
                  }}
                >
                  ＋
                </button>
              </div>
            </div>
            <div className="drawer-section" style={{ borderTop: "none", paddingTop: 0 }}>
              <span className="drawer-section-label">THREADS</span>
              <div className="pin-chip-row">
                {local.threads.map((th, i) => (
                  <span className="pin-chip" key={i}>
                    {th}
                    <button
                      className="editor-clue-remove"
                      onClick={() => update({ threads: local.threads.filter((_, j) => j !== i) })}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
              <div className="editor-clue-add">
                <input
                  className="input"
                  style={{ flex: 1, width: "auto", minWidth: 0 }}
                  placeholder="Add thread tag…"
                  value={threadDraft}
                  onChange={(e) => setThreadDraft(e.target.value)}
                />
                <button
                  className="board-new-scene"
                  style={{ marginLeft: 0 }}
                  onClick={() => {
                    if (!threadDraft.trim()) return;
                    update({ threads: [...local.threads, threadDraft.trim()] });
                    setThreadDraft("");
                  }}
                >
                  ＋
                </button>
              </div>
            </div>
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">PROVENANCE</span>
            <div className="pin-chip-row">
              {local.source && <span className="chip">source: {local.source}</span>}
              {local.lane && <span className="chip">lane: {local.lane}</span>}
              {local.classification && <span className="chip">class: {local.classification}</span>}
              {local.target_epic && <span className="chip">epic: {local.target_epic}</span>}
              {!local.source && !local.lane && !local.classification && !local.target_epic && (
                <span className="drawer-empty">No import provenance — created in the dashboard.</span>
              )}
            </div>
            <div className="deck-card-meta" style={{ gap: 16 }}>
              {local.introduced && <span>introduced {local.introduced}</span>}
              {local.closed && <span>closed {local.closed}</span>}
              {local.review_after && <span>review after {local.review_after}</span>}
            </div>
          </div>
        </div>

        <div className="editor-drawer-footer">
          {confirmingDelete ? (
            <>
              <span className="modal-danger-note">Delete this ticket? This can't be undone.</span>
              <button className="btn-ghost" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
              <button
                className="btn-danger"
                disabled={deleteTicket.isPending}
                onClick={() =>
                  deleteTicket.mutate(local.id, {
                    onSuccess: () => {
                      toast("Ticket deleted");
                      onClose();
                    },
                  })
                }
              >
                Confirm delete
              </button>
            </>
          ) : (
            <>
              <button
                className="btn-danger-ghost"
                style={{ marginRight: "auto" }}
                onClick={() => setConfirmingDelete(true)}
              >
                Delete
              </button>
              <button className="btn btn-primary" onClick={onClose}>
                Done
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}

export function Tickets({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const { data: tickets = [] } = useTicketsQuery();
  const createTicket = useCreateTicket();
  const patchStage = usePatchTicketStage();
  const importVault = useImportTicketsFromVault();

  const [areaFilter, setAreaFilter] = useState<string>("all");
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [modal, setModal] = useState<{ title: string; area: string; priority: string; description: string } | null>(null);
  const [importBanner, setImportBanner] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }

  const filtered = tickets.filter((t) => areaFilter === "all" || t.area === areaFilter);
  const drawerTicket = tickets.find((t) => t.id === drawerId) ?? null;

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const stage = over.id as string;
    if (!STAGES.includes(stage as (typeof STAGES)[number])) return;
    const ticket = tickets.find((t) => t.id === active.id);
    if (!ticket || ticket.stage === stage) return;
    patchStage.mutate({ id: ticket.id, stage });
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Tickets</h1>
          <span className="page-subtitle">
            operational backlog · now / next / deferred / done — drag to re-stage
          </span>
        </div>
        <div className="header-actions">
          <button
            className="btn-ghost"
            disabled={importVault.isPending}
            onClick={() =>
              importVault.mutate(undefined, {
                onSuccess: (res) =>
                  setImportBanner(
                    `Vault scan complete — ${JSON.stringify(res).length > 2 ? "new proposals staged as pending reviews" : "no changes"}`,
                  ),
                onError: (err) => showToast(`Import failed: ${err.message}`),
              })
            }
          >
            {importVault.isPending ? "Scanning…" : "⟳ Import from vault"}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => setModal({ title: "", area: "lore", priority: "med", description: "" })}
          >
            ＋ New ticket
          </button>
        </div>
      </header>

      <div className="lens-filters" style={{ marginTop: 0 }}>
        <span className="field-label">AREA</span>
        {["all", ...AREAS].map((a) => (
          <button
            key={a}
            className={`lens-filter${areaFilter === a ? " lens-filter--active" : ""}`}
            onClick={() => setAreaFilter(a)}
          >
            {a}
          </button>
        ))}
      </div>

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="deck-board" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          {STAGES.map((stage) => (
            <TicketLane
              key={stage}
              stage={stage}
              tickets={filtered.filter((t) => t.stage === stage)}
              allTickets={tickets}
              onOpen={(t) => setDrawerId(t.id)}
            />
          ))}
        </div>
      </DndContext>

      <span className="field-hint">
        Tickets are hand-authored as vault markdown files — "Import from vault" stages new ones as
        reviews in{" "}
        <button className="panel-link" style={{ background: "none", border: "none", padding: 0 }} onClick={() => onNavigate("sync-center")}>
          Sync Center
        </button>
        .
      </span>

      {drawerTicket && (
        <TicketDrawer
          ticket={drawerTicket}
          allTickets={tickets}
          onClose={() => setDrawerId(null)}
          onOpenTicket={(id) => setDrawerId(id)}
          toast={showToast}
        />
      )}

      {modal && (
        <Modal
          title="New ticket"
          onClose={() => setModal(null)}
          footer={
            <>
              <button className="btn-ghost" onClick={() => setModal(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={createTicket.isPending}
                onClick={() => {
                  if (!modal.title.trim()) {
                    showToast("Give the ticket a title first");
                    return;
                  }
                  createTicket.mutate(
                    {
                      title: modal.title.trim(),
                      area: modal.area,
                      priority: modal.priority,
                      stage: "now",
                      body: modal.description,
                    },
                    {
                      onSuccess: () => {
                        setModal(null);
                        showToast('Ticket created in "now"');
                      },
                      onError: (err) => showToast(`Create failed: ${err.message}`),
                    },
                  );
                }}
              >
                Create in "now"
              </button>
            </>
          }
        >
          <div className="quick-draft-note" style={{ background: "var(--amber-tint-bg)", borderColor: "var(--amber-tint-border)", color: "var(--amber-bright)" }}>
            ⚑ Project convention: tickets are usually hand-authored as vault markdown and imported.
            Ad-hoc creation here is the exception, not the rule.
          </div>
          <Field label="TITLE">
            <input
              className="input"
              value={modal.title}
              onChange={(e) => setModal({ ...modal, title: e.target.value })}
            />
          </Field>
          <Field label="AREA">
            <PillSelect
              options={AREAS}
              value={modal.area as (typeof AREAS)[number]}
              onChange={(area) => setModal({ ...modal, area })}
            />
          </Field>
          <Field label="PRIORITY">
            <PillSelect
              options={PRIORITIES}
              value={modal.priority as (typeof PRIORITIES)[number]}
              onChange={(priority) => setModal({ ...modal, priority })}
            />
          </Field>
          <Field label="DESCRIPTION">
            <textarea
              className="textarea"
              style={{ minHeight: 72 }}
              value={modal.description}
              onChange={(e) => setModal({ ...modal, description: e.target.value })}
            />
          </Field>
        </Modal>
      )}

      {importBanner && (
        <div className="import-banner">
          <span>{importBanner}</span>
          <button className="panel-link" style={{ background: "none", border: "none" }} onClick={() => onNavigate("sync-center")}>
            Review in Sync Center →
          </button>
          <button className="drawer-close" style={{ fontSize: 16 }} onClick={() => setImportBanner(null)}>
            ✕
          </button>
        </div>
      )}

      {toast && !importBanner && <div className="toast">{toast}</div>}
    </>
  );
}
