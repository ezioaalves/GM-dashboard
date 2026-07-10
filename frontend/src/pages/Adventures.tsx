import { useState } from "react";
import { Modal, Field } from "../components/Modal";
import { PillSelect } from "../components/PillSelect";
import {
  useAdventuresQuery,
  useAdventureQuery,
  useCreateAdventure,
  usePatchAdventure,
  useDeleteAdventure,
  useApplySpinePreset,
  useLinkSession,
  useUnlinkSession,
  castHooks,
  rewardHooks,
  encounterHooks,
  pcPressureHooks,
  clockLinkHooks,
} from "../api/adventures";
import { useNPCsQuery, usePCsQuery } from "../api/npcs";
import { useSessionsQuery } from "../api/sessions";
import { useClocksQuery } from "../api/clocks";
import type { AdventureDetail, AdventureStatus } from "../types/adventure";

const STATUSES: readonly AdventureStatus[] = ["draft", "ready", "played", "archived"];

/** stakes / safety_flags arrive as loose JSON — normalize to a string list. */
function jsonList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (value && typeof value === "object" && Array.isArray((value as { items?: unknown }).items)) {
    return ((value as { items: unknown[] }).items ?? []).map(String).filter(Boolean);
  }
  if (typeof value === "string") return value.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
  return [];
}

interface AdventureDraft {
  title: string;
  status: AdventureStatus;
  mode: string;
  pitch: string;
  tone_rule: string;
  safety_flags: string;
  feel_target: string;
  feel_avoid: string;
  stakes: string;
  location_name: string;
  location_notes: string;
}

function draftFromDetail(adv: AdventureDetail | null): AdventureDraft {
  const loc = (adv?.location ?? {}) as { name?: string; notes?: string };
  return {
    title: adv?.title ?? "",
    status: adv?.status ?? "draft",
    mode: adv?.mode ?? "",
    pitch: adv?.pitch ?? "",
    tone_rule: adv?.tone_rule ?? "",
    safety_flags: adv?.safety_flags ?? "",
    feel_target: adv?.feel_target ?? "",
    feel_avoid: adv?.feel_avoid ?? "",
    stakes: jsonList(adv?.stakes).join("\n"),
    location_name: loc.name ?? "",
    location_notes: loc.notes ?? "",
  };
}

function draftToPayload(draft: AdventureDraft) {
  return {
    title: draft.title || "Untitled adventure",
    status: draft.status,
    mode: draft.mode,
    pitch: draft.pitch,
    tone_rule: draft.tone_rule,
    safety_flags: draft.safety_flags,
    feel_target: draft.feel_target,
    feel_avoid: draft.feel_avoid,
    stakes: { items: draft.stakes.split("\n").map((s) => s.trim()).filter(Boolean) },
    location: { name: draft.location_name, notes: draft.location_notes },
  };
}

type ChildModal =
  | { kind: "cast"; rowId: number | null; data: Record<string, string> }
  | { kind: "encounter"; rowId: number | null; data: Record<string, string> }
  | { kind: "reward"; rowId: number | null; data: Record<string, string> }
  | { kind: "pressure"; rowId: number | null; data: Record<string, string> }
  | { kind: "clock-link"; rowId: number | null; data: Record<string, string> }
  | { kind: "session-link"; rowId: null; data: Record<string, string> };

const TABS = ["cast", "encounters", "rewards", "pressure", "clocks", "sessions"] as const;
type Tab = (typeof TABS)[number];

export function Adventures() {
  const { data: adventures = [] } = useAdventuresQuery();
  const [openId, setOpenId] = useState<number | null>(null);
  const { data: detail } = useAdventureQuery(openId);

  const createAdventure = useCreateAdventure();
  const patchAdventure = usePatchAdventure();
  const deleteAdventure = useDeleteAdventure();
  const applyPreset = useApplySpinePreset();
  const linkSession = useLinkSession();
  const unlinkSession = useUnlinkSession();

  const createCast = castHooks.useCreate();
  const patchCast = castHooks.usePatch();
  const deleteCast = castHooks.useDelete();
  const createEncounter = encounterHooks.useCreate();
  const patchEncounter = encounterHooks.usePatch();
  const deleteEncounter = encounterHooks.useDelete();
  const createReward = rewardHooks.useCreate();
  const patchReward = rewardHooks.usePatch();
  const deleteReward = rewardHooks.useDelete();
  const createPressure = pcPressureHooks.useCreate();
  const patchPressure = pcPressureHooks.usePatch();
  const deletePressure = pcPressureHooks.useDelete();
  const createClockLink = clockLinkHooks.useCreate();
  const patchClockLink = clockLinkHooks.usePatch();
  const deleteClockLink = clockLinkHooks.useDelete();

  const { data: npcs = [] } = useNPCsQuery();
  const { data: pcs = [] } = usePCsQuery();
  const { data: sessions = [] } = useSessionsQuery();
  const { data: clocks = [] } = useClocksQuery();

  const [tab, setTab] = useState<Tab>("cast");
  const [advModal, setAdvModal] = useState<{ id: number | null; draft: AdventureDraft } | null>(
    null,
  );
  const [confirmingAdvDelete, setConfirmingAdvDelete] = useState(false);
  const [childModal, setChildModal] = useState<ChildModal | null>(null);

  const npcName = (id: number) => npcs.find((n) => n.id === id)?.name ?? `npc #${id}`;
  const pcName = (id: number) => pcs.find((p) => p.id === id)?.name ?? `pc #${id}`;
  const clockName = (id: string | null) =>
    id ? (clocks.find((c) => c.id === id)?.name ?? id) : "(thread link)";

  function saveChildModal() {
    if (!childModal || openId == null) return;
    const { kind, rowId, data } = childModal;
    const done = { onSuccess: () => setChildModal(null) };
    if (kind === "cast") {
      const payload = {
        npc_id: Number(data.npc_id),
        role: data.role,
        wants_now: data.wants_now,
        hides: data.hides,
        if_helped: data.if_helped,
        if_crossed: data.if_crossed,
      };
      if (!payload.npc_id) return;
      if (rowId == null) createCast.mutate({ adventureId: openId, ...payload }, done);
      else patchCast.mutate({ adventureId: openId, rowId, ...payload }, done);
    } else if (kind === "encounter") {
      const payload = {
        name: data.name,
        objective: data.objective,
        opposition: data.opposition,
        terrain_constraint: data.terrain_constraint,
        what_changes: data.what_changes,
      };
      if (rowId == null) createEncounter.mutate({ adventureId: openId, ...payload }, done);
      else patchEncounter.mutate({ adventureId: openId, rowId, ...payload }, done);
    } else if (kind === "reward") {
      const payload = {
        name: data.name,
        type: data.type,
        who_cares: data.who_cares,
        mechanical_note: data.mechanical_note,
        future_hook: data.future_hook,
      };
      if (rowId == null) createReward.mutate({ adventureId: openId, ...payload }, done);
      else patchReward.mutate({ adventureId: openId, rowId, ...payload }, done);
    } else if (kind === "pressure") {
      const payload = {
        pc_id: Number(data.pc_id),
        pressure: data.pressure,
        growth: data.growth,
        cost: data.cost,
      };
      if (!payload.pc_id) return;
      if (rowId == null) createPressure.mutate({ adventureId: openId, ...payload }, done);
      else patchPressure.mutate({ adventureId: openId, rowId, ...payload }, done);
    } else if (kind === "clock-link") {
      const payload = {
        clock_id: data.clock_id || undefined,
        how_it_appears: data.how_it_appears,
        advance_trigger: data.advance_trigger,
        visible_impact: data.visible_impact,
      };
      if (rowId == null) createClockLink.mutate({ adventureId: openId, ...payload }, done);
      else patchClockLink.mutate({ adventureId: openId, rowId, ...payload }, done);
    } else if (kind === "session-link") {
      const sessionId = Number(data.session_id);
      if (!sessionId) return;
      linkSession.mutate({ adventureId: openId, sessionId }, done);
    }
  }

  // ── list view ──────────────────────────────────────────────────────────────

  if (openId == null || !detail) {
    return (
      <>
        <header className="page-header">
          <div>
            <h1 className="page-title">Adventures</h1>
            <span className="page-subtitle">Arc-level prep, above the session</span>
          </div>
          <div className="header-actions">
            <button
              className="btn btn-primary"
              onClick={() => setAdvModal({ id: null, draft: draftFromDetail(null) })}
            >
              ＋ New adventure
            </button>
          </div>
        </header>

        {adventures.length === 0 && (
          <div className="empty-state">No adventures yet — pitch the first one.</div>
        )}

        <div className="adventure-grid">
          {adventures.map((adv) => (
            <div className="adventure-card" key={adv.id} onClick={() => setOpenId(adv.id)}>
              <div className="adventure-card-top">
                <span className={`status-pill status-pill--active adv-status--${adv.status}`}>
                  {adv.status}
                </span>
                <span className="adventure-card-sessions">{adv.session_count} sessions</span>
              </div>
              <div className="adventure-card-main">
                <span className="adventure-card-title">{adv.title}</span>
                <span className="adventure-card-pitch">{adv.pitch}</span>
              </div>
              {adv.mode && (
                <div className="adventure-card-tags">
                  <span className="tag-pill">{adv.mode}</span>
                </div>
              )}
            </div>
          ))}
        </div>

        {advModal && renderAdvModal()}
      </>
    );
  }

  // ── detail view ────────────────────────────────────────────────────────────

  const loc = (detail.location ?? {}) as { name?: string; notes?: string };
  const stakes = jsonList(detail.stakes);
  const safetyFlags = jsonList(detail.safety_flags);
  const linkedSessionIds = new Set(detail.sessions.map((s) => s.id));

  function renderAdvModal() {
    if (!advModal) return null;
    return (
      <Modal
        title={advModal.id != null ? "Edit adventure" : "New adventure"}
        width={560}
        onClose={() => setAdvModal(null)}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setAdvModal(null)}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              disabled={createAdventure.isPending || patchAdventure.isPending}
              onClick={() => {
                const payload = draftToPayload(advModal.draft);
                if (advModal.id == null) {
                  createAdventure.mutate(payload, {
                    onSuccess: (created) => {
                      setAdvModal(null);
                      setOpenId(created.id);
                    },
                  });
                } else {
                  patchAdventure.mutate(
                    { id: advModal.id, ...payload },
                    { onSuccess: () => setAdvModal(null) },
                  );
                }
              }}
            >
              Save
            </button>
          </>
        }
      >
        <Field label="TITLE">
          <input
            className="input"
            type="text"
            value={advModal.draft.title}
            onChange={(e) =>
              setAdvModal({ ...advModal, draft: { ...advModal.draft, title: e.target.value } })
            }
          />
        </Field>
        <Field label="STATUS">
          <PillSelect
            options={STATUSES}
            value={advModal.draft.status}
            onChange={(status) => setAdvModal({ ...advModal, draft: { ...advModal.draft, status } })}
          />
        </Field>
        <Field label="MODE" hint="e.g. investigation, heist, siege, court intrigue">
          <input
            className="input"
            type="text"
            value={advModal.draft.mode}
            onChange={(e) =>
              setAdvModal({ ...advModal, draft: { ...advModal.draft, mode: e.target.value } })
            }
          />
        </Field>
        {(
          [
            ["PITCH", "pitch"],
            ["TONE RULE", "tone_rule"],
            ["FEEL TARGET", "feel_target"],
            ["FEEL AVOID", "feel_avoid"],
          ] as const
        ).map(([label, key]) => (
          <Field label={label} key={key}>
            <textarea
              className="textarea"
              style={{ minHeight: 52 }}
              value={advModal.draft[key]}
              onChange={(e) =>
                setAdvModal({ ...advModal, draft: { ...advModal.draft, [key]: e.target.value } })
              }
            />
          </Field>
        ))}
        <Field label="SAFETY FLAGS" hint="comma-separated">
          <input
            className="input"
            type="text"
            value={advModal.draft.safety_flags}
            onChange={(e) =>
              setAdvModal({ ...advModal, draft: { ...advModal.draft, safety_flags: e.target.value } })
            }
          />
        </Field>
        <Field label="STAKES" hint="one per line">
          <textarea
            className="textarea"
            value={advModal.draft.stakes}
            onChange={(e) =>
              setAdvModal({ ...advModal, draft: { ...advModal.draft, stakes: e.target.value } })
            }
          />
        </Field>
        <Field label="LOCATION NAME">
          <input
            className="input"
            type="text"
            value={advModal.draft.location_name}
            onChange={(e) =>
              setAdvModal({
                ...advModal,
                draft: { ...advModal.draft, location_name: e.target.value },
              })
            }
          />
        </Field>
        <Field label="LOCATION NOTES">
          <textarea
            className="textarea"
            style={{ minHeight: 52 }}
            value={advModal.draft.location_notes}
            onChange={(e) =>
              setAdvModal({
                ...advModal,
                draft: { ...advModal.draft, location_notes: e.target.value },
              })
            }
          />
        </Field>
      </Modal>
    );
  }

  const childField = (label: string, key: string, textarea = false) => (
    <Field label={label} key={key}>
      {textarea ? (
        <textarea
          className="textarea"
          style={{ minHeight: 52 }}
          value={childModal?.data[key] ?? ""}
          onChange={(e) =>
            childModal && setChildModal({ ...childModal, data: { ...childModal.data, [key]: e.target.value } })
          }
        />
      ) : (
        <input
          className="input"
          type="text"
          value={childModal?.data[key] ?? ""}
          onChange={(e) =>
            childModal && setChildModal({ ...childModal, data: { ...childModal.data, [key]: e.target.value } })
          }
        />
      )}
    </Field>
  );

  const childSelect = (
    label: string,
    key: string,
    options: Array<{ value: string; label: string }>,
  ) => (
    <Field label={label} key={key}>
      <select
        className="input"
        value={childModal?.data[key] ?? ""}
        onChange={(e) =>
          childModal && setChildModal({ ...childModal, data: { ...childModal.data, [key]: e.target.value } })
        }
      >
        <option value="">— pick —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );

  return (
    <>
      <button className="wrap-back" onClick={() => setOpenId(null)}>
        ← All adventures
      </button>

      <header className="page-header">
        <div className="session-header-main">
          <h1 className="page-title">{detail.title}</h1>
          <div className="status-pill-row">
            {STATUSES.map((status) => (
              <button
                key={status}
                className={`status-pill${detail.status === status ? " status-pill--active" : ""}`}
                onClick={() => patchAdventure.mutate({ id: detail.id, status })}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
        <div className="header-actions">
          <button
            className="btn-ghost"
            onClick={() => setAdvModal({ id: detail.id, draft: draftFromDetail(detail) })}
          >
            Edit
          </button>
          {confirmingAdvDelete ? (
            <>
              <button className="btn-ghost" onClick={() => setConfirmingAdvDelete(false)}>
                Cancel
              </button>
              <button
                className="btn-danger"
                onClick={() =>
                  deleteAdventure.mutate(detail.id, {
                    onSuccess: () => {
                      setConfirmingAdvDelete(false);
                      setOpenId(null);
                    },
                  })
                }
              >
                Confirm delete
              </button>
            </>
          ) : (
            <button className="btn-danger-ghost" onClick={() => setConfirmingAdvDelete(true)}>
              Delete
            </button>
          )}
        </div>
      </header>

      {/* pitch / tone / feel */}
      <div className="adventure-summary">
        <div className="field" style={{ gap: 5 }}>
          <span className="field-label">PITCH</span>
          <span className="promise-text">{detail.pitch || "—"}</span>
        </div>
        <div className="adventure-summary-grid">
          <div className="field" style={{ gap: 5 }}>
            <span className="field-label">TONE RULE</span>
            <span className="panel-note">{detail.tone_rule || "—"}</span>
          </div>
          <div className="field" style={{ gap: 5 }}>
            <span className="field-label">SAFETY FLAGS</span>
            <div className="pin-chip-row">
              {safetyFlags.length > 0 ? (
                safetyFlags.map((flag) => (
                  <span className="safety-flag" key={flag}>
                    {flag}
                  </span>
                ))
              ) : (
                <span className="drawer-empty">none</span>
              )}
            </div>
          </div>
        </div>
        <div className="adventure-summary-grid">
          <div className="field" style={{ gap: 5 }}>
            <span className="field-label" style={{ color: "var(--teal)" }}>
              FEEL TARGET
            </span>
            <span className="panel-note">{detail.feel_target || "—"}</span>
          </div>
          <div className="field" style={{ gap: 5 }}>
            <span className="field-label" style={{ color: "var(--amber-bright)" }}>
              FEEL AVOID
            </span>
            <span className="panel-note">{detail.feel_avoid || "—"}</span>
          </div>
        </div>
      </div>

      {/* stakes + location */}
      <div className="adventure-summary-grid" style={{ gap: 16 }}>
        <div className="panel">
          <span className="panel-label">STAKES</span>
          {stakes.length > 0 ? (
            <div className="stake-list">
              {stakes.map((stake, i) => (
                <div className="stake-row" key={i}>
                  <span className="stake-arrow">→</span>
                  <span>{stake}</span>
                </div>
              ))}
            </div>
          ) : (
            <span className="drawer-empty">No stakes recorded.</span>
          )}
        </div>
        <div className="panel">
          <span className="panel-label">LOCATION</span>
          <span className="adventure-card-title">{loc.name || "—"}</span>
          <span className="panel-note">{loc.notes || ""}</span>
        </div>
      </div>

      {/* spine */}
      <div className="spine-section">
        <div className="board-toolbar">
          <h2 className="column-heading-label">SPINE</h2>
          <span className="board-hint">ordered story beats</span>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            <button
              className="btn-ghost"
              disabled={applyPreset.isPending}
              onClick={() => applyPreset.mutate({ id: detail.id, preset: "six_beat" })}
            >
              Apply six-beat
            </button>
            <button
              className="btn-ghost"
              disabled={applyPreset.isPending}
              onClick={() => applyPreset.mutate({ id: detail.id, preset: "five_room" })}
            >
              Apply five-room
            </button>
          </div>
        </div>
        <div className="spine-list">
          {detail.spine.length === 0 && (
            <div className="empty-state">No spine yet — apply a preset or edit the adventure.</div>
          )}
          {detail.spine.map((beat, i) => (
            <div className="spine-row" key={i}>
              <span className="spine-n">{i + 1}</span>
              <div className="spine-body">
                <span className="spine-label">{beat.label}</span>
                {beat.text && <span className="spine-detail">{beat.text}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* sub-collection tabs */}
      <div className="tabs">
        {(
          [
            ["cast", `Cast`, detail.cast.length],
            ["encounters", `Encounters`, detail.encounters.length],
            ["rewards", `Rewards`, detail.rewards.length],
            ["pressure", `PC Pressure`, detail.pc_pressure.length],
            ["clocks", `Clock Links`, detail.clock_links.length],
            ["sessions", `Sessions`, detail.sessions.length],
          ] as Array<[Tab, string, number]>
        ).map(([key, label, count]) => (
          <button
            key={key}
            className={`tab${tab === key ? " tab--active" : ""}`}
            onClick={() => setTab(key)}
          >
            {label} <span className="lane-count">{count}</span>
          </button>
        ))}
      </div>

      {tab === "cast" && (
        <div className="child-list">
          {detail.cast.map((c) => (
            <div className="child-card" key={c.id}>
              <div className="child-card-top">
                <span className="child-card-title">{npcName(c.npc_id)}</span>
                <span className="tag-pill">{c.role || "cast"}</span>
                <button
                  className="child-edit"
                  onClick={() =>
                    setChildModal({
                      kind: "cast",
                      rowId: c.id,
                      data: {
                        npc_id: String(c.npc_id),
                        role: c.role,
                        wants_now: c.wants_now,
                        hides: c.hides,
                        if_helped: c.if_helped,
                        if_crossed: c.if_crossed,
                      },
                    })
                  }
                >
                  Edit
                </button>
                <button
                  className="child-delete"
                  onClick={() => deleteCast.mutate({ adventureId: detail.id, rowId: c.id })}
                >
                  Delete
                </button>
              </div>
              <div className="child-card-grid">
                <div>
                  <span className="child-key">WANTS NOW</span>
                  <br />
                  {c.wants_now || "—"}
                </div>
                <div>
                  <span className="child-key">HIDES</span>
                  <br />
                  {c.hides || "—"}
                </div>
                <div>
                  <span className="child-key" style={{ color: "var(--teal-bright)" }}>
                    IF HELPED
                  </span>
                  <br />
                  {c.if_helped || "—"}
                </div>
                <div>
                  <span className="child-key" style={{ color: "var(--red-bright)" }}>
                    IF CROSSED
                  </span>
                  <br />
                  {c.if_crossed || "—"}
                </div>
              </div>
            </div>
          ))}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content" }}
            onClick={() => setChildModal({ kind: "cast", rowId: null, data: {} })}
          >
            ＋ Add cast member
          </button>
        </div>
      )}

      {tab === "encounters" && (
        <div className="child-list">
          {detail.encounters.map((e) => (
            <div className="child-card" key={e.id}>
              <div className="child-card-top">
                <span className="child-card-title" style={{ flex: 1 }}>
                  {e.objective || e.name || "Encounter"}
                </span>
                <button
                  className="child-edit"
                  onClick={() =>
                    setChildModal({
                      kind: "encounter",
                      rowId: e.id,
                      data: {
                        name: e.name,
                        objective: e.objective,
                        opposition: e.opposition,
                        terrain_constraint: e.terrain_constraint,
                        what_changes: e.what_changes,
                      },
                    })
                  }
                >
                  Edit
                </button>
                <button
                  className="child-delete"
                  onClick={() => deleteEncounter.mutate({ adventureId: detail.id, rowId: e.id })}
                >
                  Delete
                </button>
              </div>
              <div className="child-card-grid child-card-grid--3">
                <div>
                  <span className="child-key">OPPOSITION</span>
                  <br />
                  {e.opposition || "—"}
                </div>
                <div>
                  <span className="child-key">TERRAIN</span>
                  <br />
                  {e.terrain_constraint || "—"}
                </div>
                <div>
                  <span className="child-key">WHAT CHANGES</span>
                  <br />
                  {e.what_changes || "—"}
                </div>
              </div>
            </div>
          ))}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content" }}
            onClick={() => setChildModal({ kind: "encounter", rowId: null, data: {} })}
          >
            ＋ Add encounter
          </button>
        </div>
      )}

      {tab === "rewards" && (
        <div className="child-list">
          <div className="reward-grid reward-grid--head">
            <span>NAME</span>
            <span>TYPE</span>
            <span>WHO CARES</span>
            <span>MECHANICAL NOTE</span>
            <span>FUTURE HOOK</span>
            <span />
          </div>
          {detail.rewards.map((r) => (
            <div className="reward-grid reward-grid--row" key={r.id}>
              <span style={{ fontWeight: 600, color: "var(--text-high)" }}>{r.name}</span>
              <span className="mono-inline" style={{ color: "var(--text-dim)" }}>
                {r.type}
              </span>
              <span>{r.who_cares}</span>
              <span>{r.mechanical_note}</span>
              <span>{r.future_hook}</span>
              <span style={{ display: "flex", gap: 8 }}>
                <button
                  className="child-edit"
                  onClick={() =>
                    setChildModal({
                      kind: "reward",
                      rowId: r.id,
                      data: {
                        name: r.name,
                        type: r.type,
                        who_cares: r.who_cares,
                        mechanical_note: r.mechanical_note,
                        future_hook: r.future_hook,
                      },
                    })
                  }
                >
                  Edit
                </button>
                <button
                  className="child-delete"
                  onClick={() => deleteReward.mutate({ adventureId: detail.id, rowId: r.id })}
                >
                  Del
                </button>
              </span>
            </div>
          ))}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content", marginTop: 8 }}
            onClick={() => setChildModal({ kind: "reward", rowId: null, data: {} })}
          >
            ＋ Add reward
          </button>
        </div>
      )}

      {tab === "pressure" && (
        <div className="child-list">
          <div className="pressure-grid">
            {detail.pc_pressure.map((p) => (
              <div className="child-card" key={p.id}>
                <div className="child-card-top">
                  <span className="child-card-title" style={{ flex: 1 }}>
                    {pcName(p.pc_id)}
                  </span>
                  <button
                    className="child-edit"
                    onClick={() =>
                      setChildModal({
                        kind: "pressure",
                        rowId: p.id,
                        data: {
                          pc_id: String(p.pc_id),
                          pressure: p.pressure,
                          growth: p.growth,
                          cost: p.cost,
                        },
                      })
                    }
                  >
                    Edit
                  </button>
                  <button
                    className="child-delete"
                    onClick={() => deletePressure.mutate({ adventureId: detail.id, rowId: p.id })}
                  >
                    Del
                  </button>
                </div>
                <div className="pressure-rows">
                  <div>
                    <span className="child-key" style={{ color: "var(--amber-bright)" }}>
                      PRESSURE
                    </span>{" "}
                    {p.pressure || "—"}
                  </div>
                  <div>
                    <span className="child-key" style={{ color: "var(--teal-bright)" }}>
                      GROWTH
                    </span>{" "}
                    {p.growth || "—"}
                  </div>
                  <div>
                    <span className="child-key" style={{ color: "var(--red-bright)" }}>
                      COST
                    </span>{" "}
                    {p.cost || "—"}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content", marginTop: 8 }}
            onClick={() => setChildModal({ kind: "pressure", rowId: null, data: {} })}
          >
            ＋ Add PC pressure
          </button>
        </div>
      )}

      {tab === "clocks" && (
        <div className="child-list">
          {detail.clock_links.map((cl) => {
            const clock = clocks.find((c) => c.id === cl.clock_id);
            return (
              <div className="child-card child-card--row" key={cl.id}>
                <div className="clock-link-dial">
                  {clock ? `${clock.filled}/${clock.segments}` : "–"}
                </div>
                <div className="clock-link-main">
                  <span className="child-card-title">{clockName(cl.clock_id)}</span>
                  <span className="panel-note">
                    {cl.how_it_appears || "—"}
                    {cl.advance_trigger ? ` · advances via ${cl.advance_trigger}` : ""}
                  </span>
                </div>
                <button
                  className="child-edit"
                  onClick={() =>
                    setChildModal({
                      kind: "clock-link",
                      rowId: cl.id,
                      data: {
                        clock_id: cl.clock_id ?? "",
                        how_it_appears: cl.how_it_appears,
                        advance_trigger: cl.advance_trigger,
                        visible_impact: cl.visible_impact,
                      },
                    })
                  }
                >
                  Edit
                </button>
                <button
                  className="child-delete"
                  onClick={() => deleteClockLink.mutate({ adventureId: detail.id, rowId: cl.id })}
                >
                  Unlink
                </button>
              </div>
            );
          })}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content" }}
            onClick={() => setChildModal({ kind: "clock-link", rowId: null, data: {} })}
          >
            ＋ Link clock
          </button>
        </div>
      )}

      {tab === "sessions" && (
        <div className="child-list">
          {detail.sessions.map((s) => {
            const session = sessions.find((x) => x.id === s.id);
            return (
              <div className="child-card child-card--row" key={s.id}>
                <span className="session-header-number">{session?.number ?? s.id}</span>
                <span className="child-card-title" style={{ flex: 1 }}>
                  {s.title || session?.name || "TBD"}
                </span>
                {session && <span className="chip">{session.status}</span>}
                <button
                  className="child-delete"
                  onClick={() => unlinkSession.mutate({ adventureId: detail.id, sessionId: s.id })}
                >
                  Unlink
                </button>
              </div>
            );
          })}
          <button
            className="board-new-scene"
            style={{ marginLeft: 0, width: "fit-content" }}
            onClick={() => setChildModal({ kind: "session-link", rowId: null, data: {} })}
          >
            ＋ Link a session
          </button>
        </div>
      )}

      {advModal && renderAdvModal()}

      {childModal && (
        <Modal
          title={
            childModal.rowId != null
              ? "Edit"
              : childModal.kind === "session-link"
                ? "Link a session"
                : "Add"
          }
          width={560}
          onClose={() => setChildModal(null)}
          footer={
            <>
              <button className="btn-ghost" onClick={() => setChildModal(null)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={saveChildModal}>
                Save
              </button>
            </>
          }
        >
          {childModal.kind === "cast" && (
            <>
              {childSelect(
                "NPC",
                "npc_id",
                npcs.map((n) => ({ value: String(n.id), label: n.name })),
              )}
              {childField("ROLE", "role")}
              {childField("WANTS NOW", "wants_now", true)}
              {childField("HIDES", "hides", true)}
              {childField("IF HELPED", "if_helped", true)}
              {childField("IF CROSSED", "if_crossed", true)}
            </>
          )}
          {childModal.kind === "encounter" && (
            <>
              {childField("NAME", "name")}
              {childField("OBJECTIVE", "objective", true)}
              {childField("OPPOSITION", "opposition", true)}
              {childField("TERRAIN CONSTRAINT", "terrain_constraint", true)}
              {childField("WHAT CHANGES", "what_changes", true)}
            </>
          )}
          {childModal.kind === "reward" && (
            <>
              {childField("NAME", "name")}
              {childField("TYPE", "type")}
              {childField("WHO CARES", "who_cares")}
              {childField("MECHANICAL NOTE", "mechanical_note", true)}
              {childField("FUTURE HOOK", "future_hook", true)}
            </>
          )}
          {childModal.kind === "pressure" && (
            <>
              {childSelect(
                "PC",
                "pc_id",
                pcs.map((p) => ({ value: String(p.id), label: p.name })),
              )}
              {childField("PRESSURE", "pressure", true)}
              {childField("GROWTH", "growth", true)}
              {childField("COST", "cost", true)}
            </>
          )}
          {childModal.kind === "clock-link" && (
            <>
              {childSelect(
                "CLOCK",
                "clock_id",
                clocks.map((c) => ({ value: c.id, label: `${c.name} (${c.filled}/${c.segments})` })),
              )}
              {childField("HOW IT APPEARS", "how_it_appears", true)}
              {childField("WHAT ADVANCES IT", "advance_trigger", true)}
              {childField("VISIBLE IMPACT", "visible_impact", true)}
            </>
          )}
          {childModal.kind === "session-link" && (
            <>
              {childSelect(
                "SESSION",
                "session_id",
                sessions
                  .filter((s) => !linkedSessionIds.has(s.id))
                  .map((s) => ({ value: String(s.id), label: `${s.number} — ${s.name || "TBD"}` })),
              )}
            </>
          )}
        </Modal>
      )}
    </>
  );
}
