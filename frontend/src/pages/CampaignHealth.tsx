import { useState } from "react";
import { Modal, Field } from "../components/Modal";
import { PillSelect } from "../components/PillSelect";
import {
  useThreadsQuery,
  useCreateThread,
  useUpdateThread,
  useDeleteThread,
} from "../api/threads";
import { usePcLanesQuery, useUpsertPcLane } from "../api/pc-lanes";
import {
  useRisksQuery,
  useRisksStaleQuery,
  useCreateRisk,
  usePatchRisk,
  useDeleteRisk,
  useMarkRiskReviewed,
} from "../api/risks";
import {
  useFeedbackQuery,
  useFeedbackOverdueQuery,
  useCreateFeedbackEntry,
  usePatchFeedbackEntry,
  useDeleteFeedbackEntry,
  useCreateActionItem,
  usePatchActionItem,
} from "../api/feedback";
import type { Thread } from "../types/thread";
import type { PcLane, PcLaneStatus } from "../types/pc-lane";
import type { Risk, RiskLikelihood, RiskStatus } from "../types/risk";
import { useSessionsQuery } from "../api/sessions";
import type { FeedbackCadence, FeedbackEntry } from "../types/feedback";

type Tab = "threads" | "lanes" | "risks" | "feedback";

const THREAD_PRIORITIES = ["low", "med", "high", "urgent"] as const;
const LANE_STATUSES: readonly PcLaneStatus[] = ["active", "stalled", "resolved", "shelved"];
const RISK_LIKELIHOODS: readonly RiskLikelihood[] = ["low", "medium", "high"];
const RISK_STATUSES: readonly RiskStatus[] = ["open", "mitigated", "triggered", "closed"];
const CADENCES: readonly FeedbackCadence[] = ["quick_check", "arc_review", "private_checkin"];

type ModalState =
  | { kind: "thread"; id: string | null; data: Record<string, string> }
  | { kind: "lane"; slug: string; name: string; data: Record<string, string> }
  | { kind: "risk"; id: number | null; data: Record<string, string> }
  | { kind: "feedback"; id: number | null; data: Record<string, string> };

export function CampaignHealth() {
  const { data: threads = [] } = useThreadsQuery();
  const { data: lanes = [] } = usePcLanesQuery();
  const { data: risks = [] } = useRisksQuery();
  const { data: staleRisks = [] } = useRisksStaleQuery();
  const { data: feedback = [] } = useFeedbackQuery();
  const { data: overdue = [] } = useFeedbackOverdueQuery();
  const { data: sessions = [] } = useSessionsQuery();

  const currentSession =
    sessions.length > 0 ? Math.max(...sessions.map((s) => s.number)) : 1;

  const createThread = useCreateThread();
  const updateThread = useUpdateThread();
  const deleteThread = useDeleteThread();
  const upsertLane = useUpsertPcLane();
  const createRisk = useCreateRisk();
  const patchRisk = usePatchRisk();
  const deleteRisk = useDeleteRisk();
  const markReviewed = useMarkRiskReviewed();
  const createFeedback = useCreateFeedbackEntry();
  const patchFeedback = usePatchFeedbackEntry();
  const deleteFeedback = useDeleteFeedbackEntry();
  const createActionItem = useCreateActionItem();
  const patchActionItem = usePatchActionItem();

  const [tab, setTab] = useState<Tab>("threads");
  const [modal, setModal] = useState<ModalState | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [expandedFeedback, setExpandedFeedback] = useState<Record<number, boolean>>({});
  const [actionDraft, setActionDraft] = useState<Record<number, string>>({});

  const staleRiskIds = new Set(staleRisks.map((r) => r.id));
  const staleThreads = threads.filter((t) => t.stale_state?.state !== "current").length;
  const stalledLanes = lanes.filter((l) => l.status === "stalled").length;

  const set = (key: string) => (e: { target: { value: string } }) =>
    modal && setModal({ ...modal, data: { ...modal.data, [key]: e.target.value } });

  const setVal = (key: string, value: string) =>
    modal && setModal({ ...modal, data: { ...modal.data, [key]: value } });

  function saveModal() {
    if (!modal) return;
    const done = {
      onSuccess: () => {
        setModal(null);
        setConfirmingDelete(false);
      },
    };
    if (modal.kind === "thread") {
      if (modal.id == null) {
        const slug = (modal.data.id || "").trim().toLowerCase().replace(/\s+/g, "-");
        if (!slug) return;
        createThread.mutate(
          {
            id: slug,
            title: modal.data.title || slug,
            status: "active",
            priority: modal.data.priority as Thread["priority"],
            pressure: modal.data.pressure,
            stakes: modal.data.stakes,
            next_move: modal.data.next_move,
          },
          done,
        );
      } else {
        updateThread.mutate(
          {
            id: modal.id,
            priority: modal.data.priority as Thread["priority"],
            pressure: modal.data.pressure,
            stakes: modal.data.stakes,
            next_move: modal.data.next_move,
          },
          done,
        );
      }
    } else if (modal.kind === "lane") {
      upsertLane.mutate(
        {
          slug: modal.slug,
          status: modal.data.status as PcLaneStatus,
          goal: modal.data.goal,
          pressure: modal.data.pressure,
          notes: modal.data.notes,
        },
        done,
      );
    } else if (modal.kind === "risk") {
      const payload = {
        title: modal.data.title,
        likelihood: modal.data.likelihood as RiskLikelihood,
        status: modal.data.status as RiskStatus,
        mitigation: modal.data.mitigation,
        contingency: modal.data.contingency,
        related_thread_id: modal.data.related_thread_id || null,
      };
      if (modal.id == null) createRisk.mutate(payload, done);
      else patchRisk.mutate({ id: modal.id, ...payload }, done);
    } else if (modal.kind === "feedback") {
      const payload = {
        cadence: modal.data.cadence as FeedbackCadence,
        session_number: modal.data.session_number ? Number(modal.data.session_number) : null,
        more_of: modal.data.more_of,
        less_of: modal.data.less_of,
        clarify: modal.data.clarify,
        notes: modal.data.notes,
      };
      if (modal.id == null) createFeedback.mutate(payload, done);
      else patchFeedback.mutate({ id: modal.id, ...payload }, done);
    }
  }

  function deleteModalTarget() {
    if (!modal) return;
    const done = {
      onSuccess: () => {
        setModal(null);
        setConfirmingDelete(false);
      },
    };
    if (modal.kind === "thread" && modal.id != null) deleteThread.mutate(modal.id, done);
    else if (modal.kind === "risk" && modal.id != null) deleteRisk.mutate(modal.id, done);
    else if (modal.kind === "feedback" && modal.id != null) deleteFeedback.mutate(modal.id, done);
  }

  const modalCanDelete =
    modal && modal.kind !== "lane" && (modal as { id: unknown }).id != null;

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Campaign Health</h1>
          <span className="page-subtitle">
            Threads · PC Lanes · Risks · Feedback — the follow-up phase
          </span>
        </div>
      </header>

      {/* summary strip */}
      <div className="health-strip">
        <button className="health-stat" onClick={() => setTab("threads")}>
          <span className="field-label">THREADS</span>
          <div className="health-stat-nums">
            <span className="health-stat-big">{threads.length}</span>
            {staleThreads > 0 && <span className="health-stat-note health-stat-note--azure">{staleThreads} stale</span>}
          </div>
        </button>
        <button className="health-stat" onClick={() => setTab("lanes")}>
          <span className="field-label">PC LANES</span>
          <div className="health-stat-nums">
            <span className="health-stat-big">{lanes.length}</span>
            {stalledLanes > 0 && <span className="health-stat-note health-stat-note--amber">{stalledLanes} stalled</span>}
          </div>
        </button>
        <button className="health-stat" onClick={() => setTab("risks")}>
          <span className="field-label">RISKS</span>
          <div className="health-stat-nums">
            <span className="health-stat-big">{risks.length}</span>
            {staleRisks.length > 0 && <span className="health-stat-note health-stat-note--azure">{staleRisks.length} stale</span>}
          </div>
        </button>
        <button className="health-stat" onClick={() => setTab("feedback")}>
          <span className="field-label">FEEDBACK</span>
          <div className="health-stat-nums">
            <span className="health-stat-big">{feedback.length}</span>
            {overdue.length > 0 && <span className="health-stat-note health-stat-note--amber">{overdue.length} overdue</span>}
          </div>
        </button>
      </div>

      <div className="tabs">
        {(
          [
            ["threads", "Threads"],
            ["lanes", "PC Lanes"],
            ["risks", "Risks"],
            ["feedback", "Feedback"],
          ] as Array<[Tab, string]>
        ).map(([key, label]) => (
          <button key={key} className={`tab${tab === key ? " tab--active" : ""}`} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {/* threads */}
      {tab === "threads" && (
        <div className="child-list">
          {threads.length === 0 && <div className="empty-state">No threads tracked yet.</div>}
          {threads.map((t) => {
            const stale = t.stale_state?.state !== "current";
            return (
              <div className="child-card" key={t.id}>
                <div className="child-card-top">
                  <span className="next-move-slug" style={{ fontSize: 12.5, fontWeight: 600 }}>
                    {t.id}
                  </span>
                  <span className={`priority-chip priority-chip--${t.priority === "urgent" ? "high" : t.priority}`}>
                    {t.priority}
                  </span>
                  <span className={`chip ${stale ? "" : "chip--teal"}`}>
                    {stale ? t.stale_state?.state.replace("_", " ").toUpperCase() : "ACTIVE"}
                  </span>
                  <span className="board-hint" style={{ marginLeft: "auto" }}>
                    {t.sessions.length > 0 ? `last touched S${Math.max(...t.sessions)}` : "never touched"}
                  </span>
                  <button
                    className="child-edit"
                    style={{ marginLeft: 0 }}
                    onClick={() =>
                      setModal({
                        kind: "thread",
                        id: t.id,
                        data: {
                          priority: t.priority,
                          pressure: t.pressure,
                          stakes: t.stakes,
                          next_move: t.next_move ?? "",
                        },
                      })
                    }
                  >
                    Edit
                  </button>
                </div>
                <div className="child-card-grid">
                  <div>
                    <span className="child-key">PRESSURE</span>
                    <br />
                    {t.pressure || "—"}
                  </div>
                  <div>
                    <span className="child-key">STAKES</span>
                    <br />
                    {t.stakes || "—"}
                  </div>
                </div>
                <div className="drawer-section" style={{ gap: 4, paddingTop: 10 }}>
                  <span className="field-label" style={{ color: "var(--teal)" }}>
                    NEXT MOVE
                  </span>
                  <span className="promise-text" style={{ fontSize: 13 }}>
                    {t.next_move || "— none set —"}
                  </span>
                </div>
                {t.clock_label && (
                  <div className="pin-chip-row" style={{ borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                    <span className="chip">
                      ⏱ {t.clock_label} {t.clock_value ?? 0}/{t.clock_max ?? 0}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content" }}
            onClick={() =>
              setModal({ kind: "thread", id: null, data: { id: "", title: "", priority: "med", pressure: "", stakes: "", next_move: "" } })
            }
          >
            ＋ New thread
          </button>
        </div>
      )}

      {/* pc lanes */}
      {tab === "lanes" && (
        <div className="pressure-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
          {lanes.map((lane: PcLane) => (
            <div className="child-card" key={lane.slug}>
              <div className="child-card-top">
                <span className="child-card-title" style={{ fontSize: 15 }}>
                  {lane.name}
                </span>
                <span className={`lane-status-chip lane-status-chip--${lane.status}`}>{lane.status}</span>
                <button
                  className="child-edit"
                  onClick={() =>
                    setModal({
                      kind: "lane",
                      slug: lane.slug,
                      name: lane.name,
                      data: {
                        status: lane.status,
                        goal: lane.goal,
                        pressure: lane.pressure,
                        notes: lane.notes,
                      },
                    })
                  }
                >
                  Edit
                </button>
              </div>
              <div className="field" style={{ gap: 3 }}>
                <span className="field-label">GOAL</span>
                <span style={{ fontSize: 13, color: "var(--text-body)", lineHeight: 1.5 }}>
                  {lane.goal || "—"}
                </span>
              </div>
              <div className="field" style={{ gap: 3 }}>
                <span className="field-label" style={{ color: "var(--amber-bright)" }}>
                  PRESSURE
                </span>
                <span className="panel-note">{lane.pressure || "—"}</span>
              </div>
              <div className="field" style={{ gap: 3 }}>
                <span className="field-label">NOTES</span>
                <span className="panel-note">{lane.notes || "—"}</span>
              </div>
              <div className="drawer-section" style={{ gap: 5, paddingTop: 10 }}>
                <span className="field-label">
                  OWNED THREADS <span className="field-label-aside">(read-only, name-matched)</span>
                </span>
                {lane.owned_threads.length > 0 ? (
                  <div className="pin-chip-row">
                    {lane.owned_threads.map((th) => (
                      <span className="pin-chip" key={th.id}>
                        {th.id}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="drawer-empty">None matched yet.</span>
                )}
              </div>
              <span className="field-hint">
                {lane.last_touched_session != null ? `last touched S${lane.last_touched_session}` : "not touched yet"}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* risks */}
      {tab === "risks" && (
        <div className="child-list">
          {risks.length === 0 && <div className="empty-state">No risks registered.</div>}
          {risks.map((r: Risk) => {
            const isStale = staleRiskIds.has(r.id);
            return (
              <div className={`child-card${isStale ? " child-card--stale" : ""}`} key={r.id}>
                <div className="child-card-top" style={{ flexWrap: "wrap" }}>
                  <span className="child-card-title" style={{ flex: 1, minWidth: 200 }}>
                    {r.title}
                  </span>
                  <span className={`priority-chip priority-chip--${r.likelihood === "medium" ? "med" : r.likelihood}`}>
                    {r.likelihood}
                  </span>
                  <span className={`risk-status-chip risk-status-chip--${r.status}`}>{r.status}</span>
                  {isStale && <span className="badge-pill badge-pill--stale"><span className="badge-pill-dot" />STALE</span>}
                </div>
                <div className="child-card-grid">
                  <div>
                    <span className="child-key">MITIGATION</span>
                    <br />
                    {r.mitigation || "—"}
                  </div>
                  <div>
                    <span className="child-key">CONTINGENCY</span>
                    <br />
                    {r.contingency || "—"}
                  </div>
                </div>
                <div className="rule-actions" style={{ alignItems: "center" }}>
                  <span className="field-hint">
                    {r.last_reviewed_session != null ? `last reviewed S${r.last_reviewed_session}` : "never reviewed"}
                    {r.related_thread_id && (
                      <>
                        {" "}
                        · linked to <span className="next-move-slug">{r.related_thread_id}</span>
                      </>
                    )}
                  </span>
                  <button
                    className="child-edit"
                    style={{ marginLeft: "auto" }}
                    onClick={() =>
                      setModal({
                        kind: "risk",
                        id: r.id,
                        data: {
                          title: r.title,
                          likelihood: r.likelihood,
                          status: r.status,
                          mitigation: r.mitigation,
                          contingency: r.contingency,
                          related_thread_id: r.related_thread_id ?? "",
                        },
                      })
                    }
                  >
                    Edit
                  </button>
                  <button
                    className="btn-ghost"
                    style={{ padding: "5px 13px", fontSize: 12.5 }}
                    disabled={markReviewed.isPending}
                    onClick={() => markReviewed.mutate({ id: r.id, session_number: currentSession })}
                  >
                    Mark reviewed
                  </button>
                </div>
              </div>
            );
          })}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content" }}
            onClick={() =>
              setModal({
                kind: "risk",
                id: null,
                data: { title: "", likelihood: "low", status: "open", mitigation: "", contingency: "", related_thread_id: "" },
              })
            }
          >
            ＋ New risk
          </button>
        </div>
      )}

      {/* feedback */}
      {tab === "feedback" && (
        <div className="child-list" style={{ gap: 16 }}>
          {overdue.map((o) => (
            <div className="banner banner--amber" key={o.cadence}>
              <span className="banner-mark">⚑ OVERDUE</span>
              <span>
                <code className="mono-inline">{o.cadence}</code> is {o.sessions_since_last} session
                {o.sessions_since_last === 1 ? "" : "s"} past its threshold ({o.threshold}) —
                consider logging one after the next session.
              </span>
            </div>
          ))}
          {feedback.length === 0 && <div className="empty-state">No feedback logged yet.</div>}
          {feedback.map((f: FeedbackEntry) => {
            const expanded = !!expandedFeedback[f.id];
            const openItems = f.action_items.filter((a) => a.status === "open").length;
            return (
              <div className="review-card" key={f.id}>
                <div
                  className="review-card-header"
                  onClick={() => setExpandedFeedback({ ...expandedFeedback, [f.id]: !expanded })}
                >
                  <span className={`cadence-chip cadence-chip--${f.cadence}`}>{f.cadence}</span>
                  <span className="child-card-title" style={{ fontSize: 13.5 }}>
                    {f.session_number != null ? `S${f.session_number}` : "—"}
                  </span>
                  <span className="board-hint" style={{ marginLeft: "auto" }}>
                    {openItems} open action item{openItems === 1 ? "" : "s"}
                  </span>
                  <button
                    className="child-edit"
                    style={{ marginLeft: 0 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setModal({
                        kind: "feedback",
                        id: f.id,
                        data: {
                          cadence: f.cadence,
                          session_number: f.session_number != null ? String(f.session_number) : "",
                          more_of: f.more_of,
                          less_of: f.less_of,
                          clarify: f.clarify,
                          notes: f.notes,
                        },
                      });
                    }}
                  >
                    Edit
                  </button>
                  <span className="board-hint">{expanded ? "▾" : "▸"}</span>
                </div>
                {expanded && (
                  <div className="feedback-detail">
                    <div className="child-card-grid child-card-grid--3">
                      <div>
                        <span className="child-key" style={{ color: "var(--teal-bright)" }}>
                          MORE OF
                        </span>
                        <br />
                        {f.more_of || "—"}
                      </div>
                      <div>
                        <span className="child-key" style={{ color: "var(--red-bright)" }}>
                          LESS OF
                        </span>
                        <br />
                        {f.less_of || "—"}
                      </div>
                      <div>
                        <span className="child-key" style={{ color: "var(--amber-bright)" }}>
                          CLARIFY
                        </span>
                        <br />
                        {f.clarify || "—"}
                      </div>
                    </div>
                    {f.notes && <span className="panel-note">{f.notes}</span>}
                    <div className="drawer-section" style={{ gap: 6, paddingTop: 10 }}>
                      <span className="field-label">ACTION ITEMS</span>
                      {f.action_items.map((ai) => (
                        <button
                          className="action-item-row"
                          key={ai.id}
                          onClick={() =>
                            patchActionItem.mutate({
                              entryId: f.id,
                              itemId: ai.id,
                              status: ai.status === "done" ? "open" : "done",
                            })
                          }
                        >
                          <span
                            className="action-item-dot"
                            style={{ background: ai.status === "done" ? "var(--teal)" : "var(--text-faint)" }}
                          />
                          <span
                            style={
                              ai.status === "done"
                                ? { textDecoration: "line-through", color: "var(--text-faint)" }
                                : undefined
                            }
                          >
                            {ai.item}
                          </span>
                        </button>
                      ))}
                      <div className="editor-clue-add">
                        <input
                          className="input"
                          style={{ flex: 1, width: "auto" }}
                          placeholder="Add action item…"
                          value={actionDraft[f.id] ?? ""}
                          onChange={(e) => setActionDraft({ ...actionDraft, [f.id]: e.target.value })}
                        />
                        <button
                          className="board-new-scene"
                          style={{ marginLeft: 0 }}
                          onClick={() => {
                            const text = (actionDraft[f.id] ?? "").trim();
                            if (!text) return;
                            createActionItem.mutate(
                              { entryId: f.id, item: text },
                              { onSuccess: () => setActionDraft({ ...actionDraft, [f.id]: "" }) },
                            );
                          }}
                        >
                          ＋
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content" }}
            onClick={() =>
              setModal({
                kind: "feedback",
                id: null,
                data: { cadence: "quick_check", session_number: "", more_of: "", less_of: "", clarify: "", notes: "" },
              })
            }
          >
            ＋ New feedback entry
          </button>
        </div>
      )}

      {modal && (
        <Modal
          title={
            modal.kind === "lane"
              ? `Edit lane — ${modal.name}`
              : `${(modal as { id: unknown }).id != null ? "Edit" : "New"} ${
                  modal.kind === "feedback" ? "feedback entry" : modal.kind
                }`
          }
          onClose={() => {
            setModal(null);
            setConfirmingDelete(false);
          }}
          footer={
            confirmingDelete ? (
              <>
                <span className="modal-danger-note">Delete this {modal.kind}? This can't be undone.</span>
                <button className="btn-ghost" onClick={() => setConfirmingDelete(false)}>
                  Cancel
                </button>
                <button className="btn-danger" onClick={deleteModalTarget}>
                  Confirm delete
                </button>
              </>
            ) : (
              <>
                {modalCanDelete && (
                  <button
                    className="btn-danger-ghost"
                    style={{ marginRight: "auto" }}
                    onClick={() => setConfirmingDelete(true)}
                  >
                    Delete
                  </button>
                )}
                <button
                  className="btn-ghost"
                  onClick={() => {
                    setModal(null);
                    setConfirmingDelete(false);
                  }}
                >
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={saveModal}>
                  Save
                </button>
              </>
            )
          }
        >
          {modal.kind === "thread" && (
            <>
              {modal.id == null && (
                <>
                  <Field label="SLUG">
                    <input className="input" value={modal.data.id} onChange={set("id")} placeholder="e.g. obsidian-court" />
                  </Field>
                  <Field label="TITLE">
                    <input className="input" value={modal.data.title} onChange={set("title")} />
                  </Field>
                </>
              )}
              <Field label="PRIORITY">
                <PillSelect
                  options={THREAD_PRIORITIES}
                  value={modal.data.priority as (typeof THREAD_PRIORITIES)[number]}
                  onChange={(v) => setVal("priority", v)}
                />
              </Field>
              <Field label="PRESSURE">
                <textarea className="textarea" value={modal.data.pressure} onChange={set("pressure")} />
              </Field>
              <Field label="STAKES">
                <textarea className="textarea" value={modal.data.stakes} onChange={set("stakes")} />
              </Field>
              <Field label="NEXT MOVE">
                <textarea className="textarea" value={modal.data.next_move} onChange={set("next_move")} />
              </Field>
            </>
          )}
          {modal.kind === "lane" && (
            <>
              <Field label="STATUS">
                <PillSelect
                  options={LANE_STATUSES}
                  value={modal.data.status as PcLaneStatus}
                  onChange={(v) => setVal("status", v)}
                />
              </Field>
              <Field label="GOAL">
                <textarea className="textarea" value={modal.data.goal} onChange={set("goal")} />
              </Field>
              <Field label="PRESSURE">
                <textarea className="textarea" value={modal.data.pressure} onChange={set("pressure")} />
              </Field>
              <Field label="NOTES">
                <textarea className="textarea" value={modal.data.notes} onChange={set("notes")} />
              </Field>
            </>
          )}
          {modal.kind === "risk" && (
            <>
              <Field label="TITLE">
                <input className="input" value={modal.data.title} onChange={set("title")} />
              </Field>
              <Field label="LIKELIHOOD">
                <PillSelect
                  options={RISK_LIKELIHOODS}
                  value={modal.data.likelihood as RiskLikelihood}
                  onChange={(v) => setVal("likelihood", v)}
                />
              </Field>
              <Field label="STATUS">
                <PillSelect
                  options={RISK_STATUSES}
                  value={modal.data.status as RiskStatus}
                  onChange={(v) => setVal("status", v)}
                />
              </Field>
              <Field label="MITIGATION">
                <textarea className="textarea" value={modal.data.mitigation} onChange={set("mitigation")} />
              </Field>
              <Field label="CONTINGENCY">
                <textarea className="textarea" value={modal.data.contingency} onChange={set("contingency")} />
              </Field>
              <Field label="RELATED THREAD" hint="optional thread slug">
                <input className="input" value={modal.data.related_thread_id} onChange={set("related_thread_id")} />
              </Field>
            </>
          )}
          {modal.kind === "feedback" && (
            <>
              <Field label="CADENCE">
                <PillSelect
                  options={CADENCES}
                  value={modal.data.cadence as FeedbackCadence}
                  onChange={(v) => setVal("cadence", v)}
                  labels={{ quick_check: "quick check", arc_review: "arc review", private_checkin: "private check-in" }}
                />
              </Field>
              <Field label="SESSION NUMBER">
                <input className="input" type="number" value={modal.data.session_number} onChange={set("session_number")} />
              </Field>
              <Field label="MORE OF">
                <textarea className="textarea" value={modal.data.more_of} onChange={set("more_of")} />
              </Field>
              <Field label="LESS OF">
                <textarea className="textarea" value={modal.data.less_of} onChange={set("less_of")} />
              </Field>
              <Field label="CLARIFY">
                <textarea className="textarea" value={modal.data.clarify} onChange={set("clarify")} />
              </Field>
              <Field label="NOTES">
                <textarea className="textarea" value={modal.data.notes} onChange={set("notes")} />
              </Field>
            </>
          )}
        </Modal>
      )}
    </>
  );
}
