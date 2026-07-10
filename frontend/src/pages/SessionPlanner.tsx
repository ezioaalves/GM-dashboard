import { useMemo, useState } from "react";
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
import { SceneTypeBadge, TierBadge, SCENE_TYPES, sceneClueRows } from "../components/SceneBits";
import { SessionWrap } from "./SessionWrap";
import {
  useSessionsQuery,
  useCreateSession,
  usePatchSessionStatus,
  useReplaceSceneOrder,
} from "../api/sessions";
import {
  useScenesQuery,
  useCreateScene,
  usePatchScene,
  useDeleteScene,
  useExportSceneToFoundry,
} from "../api/scenes";
import type { Session, SessionStatus, ClueMapEntry } from "../types/session";
import type { Scene, SceneCreate, ScenePlacement } from "../types/scene";

const SESSION_STATUSES: readonly SessionStatus[] = [
  "planned",
  "ready",
  "played",
  "cancelled",
  "archived",
];

const LANES: readonly ScenePlacement[] = ["ordered", "floating", "backlog"];

const LANE_LABELS: Record<ScenePlacement, string> = {
  ordered: "ORDERED",
  floating: "FLOATING",
  backlog: "BACKLOG",
};

// ── Scene draft (modal form state) ────────────────────────────────────────────

interface SceneDraft {
  title: string;
  session_id: number | null;
  placement: ScenePlacement;
  scene_type: string;
  description: string;
  core_clue: string;
  superior_clue: string;
  optional_clue: string;
  false_lead: string;
  if_succeed: string;
  if_fail: string;
  if_ignore: string;
  if_short: string;
}

function draftFromScene(scene: Scene): SceneDraft {
  return {
    title: scene.title,
    session_id: scene.session_id,
    placement: scene.placement,
    scene_type: scene.scene_type,
    description: scene.description,
    core_clue: scene.core_clue,
    superior_clue: scene.superior_clue,
    optional_clue: scene.optional_clue,
    false_lead: scene.false_lead,
    if_succeed: scene.if_succeed,
    if_fail: scene.if_fail,
    if_ignore: scene.if_ignore,
    if_short: scene.if_short,
  };
}

function emptyDraft(sessionId: number | null): SceneDraft {
  return {
    title: "",
    session_id: sessionId,
    placement: "backlog",
    scene_type: "added",
    description: "",
    core_clue: "",
    superior_clue: "",
    optional_clue: "",
    false_lead: "",
    if_succeed: "",
    if_fail: "",
    if_ignore: "",
    if_short: "",
  };
}

/** PUT is a full replace — merge the draft over every writable field of the scene. */
function scenePutPayload(scene: Scene, draft: SceneDraft): SceneCreate {
  return {
    title: draft.title,
    scene_type: draft.scene_type as SceneCreate["scene_type"],
    status: scene.status,
    session_id: draft.session_id,
    placement: draft.session_id != null ? draft.placement : "backlog",
    description: draft.description,
    location: scene.location,
    cast: scene.cast,
    clock: scene.clock,
    cuttable: scene.cuttable,
    purpose: scene.purpose,
    pc_pressure: scene.pc_pressure,
    entry_pressure: scene.entry_pressure,
    exit_condition: scene.exit_condition,
    core_clue: draft.core_clue,
    superior_clue: draft.superior_clue,
    optional_clue: draft.optional_clue,
    false_lead: draft.false_lead,
    opening_image: scene.opening_image,
    sensory_words: scene.sensory_words,
    interactable_objects: scene.interactable_objects,
    rules_likely: scene.rules_likely,
    foundry_needs: scene.foundry_needs,
    cut_or_replace_plan: scene.cut_or_replace_plan,
    if_succeed: draft.if_succeed,
    if_fail: draft.if_fail,
    if_ignore: draft.if_ignore,
    if_short: draft.if_short,
    notes: scene.notes,
    planned_notes: scene.planned_notes,
    actual_notes: scene.actual_notes,
    pinned_material: scene.pinned_material,
  };
}

// ── Fit check ────────────────────────────────────────────────────────────────

interface FitCheckItem {
  kind: "ok" | "flag";
  title: string;
  note: string;
}

function fitCheckItems(session: Session | null): FitCheckItem[] {
  const raw = session?.fit_check;
  if (!raw || !Array.isArray((raw as { items?: unknown }).items)) return [];
  return ((raw as { items: unknown[] }).items ?? []).filter(
    (it): it is FitCheckItem => typeof it === "object" && it != null && "title" in it,
  );
}

// ── Draggable scene card / droppable lane ────────────────────────────────────

function SceneCard({
  scene,
  dim,
  showSession,
  draggable,
  onSelect,
}: {
  scene: Scene;
  dim: boolean;
  showSession: boolean;
  draggable: boolean;
  onSelect: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: scene.id,
    disabled: !draggable,
  });

  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 5 }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`scene-card scene-card--${dim ? "dim" : scene.scene_type}${isDragging ? " scene-card--dragging" : ""}`}
      onClick={onSelect}
      {...listeners}
      {...attributes}
    >
      <div className="scene-card-top">
        <SceneTypeBadge type={scene.scene_type} dim={dim} />
        <span className="scene-card-title">{scene.title}</span>
        {showSession && scene.session_id != null && (
          <span className="scene-card-session">S{scene.session_id}</span>
        )}
      </div>
      {scene.description && <span className="scene-card-summary">{scene.description}</span>}
    </div>
  );
}

function Lane({
  placement,
  scenes,
  showSession,
  draggable,
  onSelect,
}: {
  placement: ScenePlacement;
  scenes: Scene[];
  showSession: boolean;
  draggable: boolean;
  onSelect: (scene: Scene) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: placement });

  return (
    <div ref={setNodeRef} className={`lane${isOver ? " lane--over" : ""}`}>
      <div className="lane-header">
        <span className={`lane-label lane-label--${placement}`}>{LANE_LABELS[placement]}</span>
        <span className="lane-count">{scenes.length}</span>
      </div>
      {scenes.map((scene) => (
        <SceneCard
          key={scene.id}
          scene={scene}
          dim={placement === "backlog"}
          showSession={showSession}
          draggable={draggable}
          onSelect={() => onSelect(scene)}
        />
      ))}
    </div>
  );
}

// ── Scene detail drawer ──────────────────────────────────────────────────────

function SceneDrawer({
  scene,
  onClose,
  onEdit,
  onDelete,
}: {
  scene: Scene;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const exportScene = useExportSceneToFoundry();
  const clues = sceneClueRows(scene);
  const hasBranching = !!(scene.if_succeed || scene.if_fail || scene.if_ignore || scene.if_short);
  const laneLabel = scene.placement.charAt(0).toUpperCase() + scene.placement.slice(1);
  const skipped = exportScene.data?.skipped_unmirrored ?? [];

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-top">
          <SceneTypeBadge type={scene.scene_type} />
          <button className="drawer-link" onClick={onEdit}>
            Edit
          </button>
          <button className="drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <h2 className="drawer-title">{scene.title}</h2>
        {scene.description && <p className="drawer-summary">{scene.description}</p>}

        <div className="drawer-section">
          <span className="drawer-section-label">LANE &amp; TYPE</span>
          <div className="drawer-chip-row">
            <span className="drawer-chip">{laneLabel}</span>
            <span className="drawer-chip">{scene.scene_type.toUpperCase()}</span>
          </div>
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">CLUES (TIERED)</span>
          {clues.length > 0 ? (
            clues.map((clue) => (
              <div className="clue-row" key={clue.tier}>
                <TierBadge tier={clue.tier} />
                <span className="clue-text">{clue.text}</span>
              </div>
            ))
          ) : (
            <span className="drawer-empty">No clues tied to this scene.</span>
          )}
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">BRANCHING OUTCOMES</span>
          {hasBranching ? (
            <div className="branching-list">
              <div className="branching-row">
                <span className="branching-key branching-key--succeed">succeed</span>
                <span>{scene.if_succeed || "—"}</span>
              </div>
              <div className="branching-row">
                <span className="branching-key branching-key--fail">fail</span>
                <span>{scene.if_fail || "—"}</span>
              </div>
              <div className="branching-row">
                <span className="branching-key branching-key--ignore">ignore</span>
                <span>{scene.if_ignore || "—"}</span>
              </div>
              <div className="branching-row">
                <span className="branching-key branching-key--short">short</span>
                <span>{scene.if_short || "—"}</span>
              </div>
            </div>
          ) : (
            <span className="drawer-empty">This scene doesn't branch.</span>
          )}
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">PINNED MATERIAL</span>
          {scene.pinned_material.length > 0 ? (
            scene.pinned_material.map((pin) => (
              <div className="pinned-row" key={pin.path}>
                <div className="pinned-thumb" />
                <div className="pinned-meta">
                  <span className="pinned-name">{pin.title || pin.path}</span>
                  <span className="pinned-path">{pin.path}</span>
                </div>
              </div>
            ))
          ) : (
            <span className="drawer-empty">Nothing pinned yet.</span>
          )}
        </div>

        <div className="drawer-section">
          <span className="drawer-section-label">FOUNDRY EXPORT</span>
          <div className="drawer-export-row">
            <span className={`export-badge export-badge--${scene.foundry_export_status}`}>
              {scene.foundry_export_status.replace("_", " ")}
            </span>
            <button
              className="btn btn-primary"
              disabled={exportScene.isPending}
              onClick={() => exportScene.mutate({ id: scene.id })}
            >
              {exportScene.isPending ? "Exporting…" : "Export to Foundry"}
            </button>
          </div>
          {exportScene.isError && <span className="error-state">{exportScene.error.message}</span>}
          {skipped.length > 0 && (
            <span className="drawer-warning">
              ⚑ {skipped.length} pinned asset{skipped.length === 1 ? " isn't" : "s aren't"} mirrored
              yet and {skipped.length === 1 ? "was" : "were"} skipped in the export.
            </span>
          )}
        </div>

        <button className="btn-danger-ghost" onClick={onDelete}>
          Delete scene
        </button>
      </div>
    </>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export function SessionPlanner() {
  const { data: sessions = [] } = useSessionsQuery();
  const { data: scenes = [] } = useScenesQuery();

  const createSession = useCreateSession();
  const patchStatus = usePatchSessionStatus();
  const replaceOrder = useReplaceSceneOrder();
  const createScene = useCreateScene();
  const patchScene = usePatchScene();
  const deleteScene = useDeleteScene();

  const sorted = useMemo(() => [...sessions].sort((a, b) => a.number - b.number), [sessions]);

  const [activeId, setActiveId] = useState<number | null>(null);
  const [tab, setTab] = useState<"board" | "fit" | "wrap">("board");
  const [wrapOpen, setWrapOpen] = useState(false);
  const [lens, setLens] = useState<"session" | "all">("session");
  const [lensFilter, setLensFilter] = useState<string>("all");
  const [selectedSceneId, setSelectedSceneId] = useState<number | null>(null);
  const [sceneModal, setSceneModal] = useState<{ id: number | null; draft: SceneDraft } | null>(
    null,
  );
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [sessionModal, setSessionModal] = useState<{
    title: string;
    status: SessionStatus;
    promise: string;
  } | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const active: Session | null =
    sorted.find((s) => s.id === activeId) ??
    sorted.find((s) => s.status === "ready") ??
    sorted.find((s) => s.status === "planned") ??
    sorted[sorted.length - 1] ??
    null;

  const isAllLens = lens === "all";

  const pool = useMemo(() => {
    if (!isAllLens) {
      if (!active) return [];
      return scenes.filter(
        (s) => s.session_id === active.id || (s.placement === "backlog" && s.session_id == null),
      );
    }
    if (lensFilter === "all") return scenes;
    return scenes.filter((s) => String(s.session_id) === lensFilter);
  }, [scenes, isAllLens, lensFilter, active]);

  const byLane = (lane: ScenePlacement) =>
    pool.filter((s) => s.placement === lane).sort((a, b) => a.sort_order - b.sort_order);

  const ordered = byLane("ordered");
  const floating = byLane("floating");
  const backlog = byLane("backlog");

  const selectedScene = scenes.find((s) => s.id === selectedSceneId) ?? null;
  const fitItems = fitCheckItems(active);
  const fitFlags = fitItems.filter((it) => it.kind === "flag").length;
  const clueMap = (active?.clue_map ?? []) as unknown as ClueMapEntry[];

  const sessionNumbers = useMemo(
    () => [...new Set(scenes.map((s) => s.session_id).filter((n): n is number => n != null))].sort((a, b) => a - b),
    [scenes],
  );

  function handleDragEnd(event: DragEndEvent) {
    if (!active || isAllLens) return;
    const { active: dragged, over } = event;
    if (!over) return;
    const targetLane = over.id as ScenePlacement;
    if (!LANES.includes(targetLane)) return;
    const scene = scenes.find((s) => s.id === dragged.id);
    if (!scene || scene.placement === targetLane) return;

    const without = (list: Scene[]) => list.filter((s) => s.id !== scene.id).map((s) => s.id);
    const lists: Record<ScenePlacement, number[]> = {
      ordered: without(ordered),
      floating: without(floating),
      backlog: without(backlog),
    };
    lists[targetLane].push(scene.id);

    replaceOrder.mutate({
      sessionId: active.id,
      ordered_scene_ids: lists.ordered,
      floating_scene_ids: lists.floating,
      backlog_scene_ids: lists.backlog,
    });
  }

  function saveSceneModal() {
    if (!sceneModal) return;
    const { id, draft } = sceneModal;
    if (id == null) {
      createScene.mutate(
        {
          title: draft.title || "Untitled scene",
          scene_type: draft.scene_type as SceneCreate["scene_type"],
          session_id: draft.session_id,
          placement: draft.session_id != null ? draft.placement : "backlog",
          description: draft.description,
          core_clue: draft.core_clue,
          superior_clue: draft.superior_clue,
          optional_clue: draft.optional_clue,
          false_lead: draft.false_lead,
          if_succeed: draft.if_succeed,
          if_fail: draft.if_fail,
          if_ignore: draft.if_ignore,
          if_short: draft.if_short,
        },
        { onSuccess: () => setSceneModal(null) },
      );
    } else {
      const scene = scenes.find((s) => s.id === id);
      if (!scene) return;
      patchScene.mutate(
        { id, data: scenePutPayload(scene, draft) },
        { onSuccess: () => setSceneModal(null) },
      );
    }
  }

  if (sorted.length === 0) {
    return (
      <>
        <header className="page-header">
          <div>
            <h1 className="page-title">Sessions</h1>
            <span className="page-subtitle">session planner</span>
          </div>
          <div className="header-actions">
            <button
              className="btn btn-primary"
              onClick={() => setSessionModal({ title: "", status: "planned", promise: "" })}
            >
              ＋ New session
            </button>
          </div>
        </header>
        <div className="empty-state">No sessions yet — create the first one.</div>
        {sessionModal && renderSessionModal()}
      </>
    );
  }

  if (wrapOpen && active) {
    return <SessionWrap session={active} onBack={() => setWrapOpen(false)} />;
  }

  function renderSessionModal() {
    if (!sessionModal) return null;
    const nextNumber = sorted.length > 0 ? Math.max(...sorted.map((s) => s.number)) + 1 : 1;
    return (
      <Modal
        title="New session"
        titleAside={<span className="modal-title-aside">SESSION {nextNumber}</span>}
        onClose={() => setSessionModal(null)}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setSessionModal(null)}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              disabled={createSession.isPending}
              onClick={() =>
                createSession.mutate(
                  {
                    number: nextNumber,
                    name: sessionModal.title,
                    status: sessionModal.status,
                    promise: sessionModal.promise,
                  },
                  {
                    onSuccess: (created) => {
                      setSessionModal(null);
                      setActiveId(created.id);
                    },
                  },
                )
              }
            >
              Create session
            </button>
          </>
        }
      >
        <Field label="TITLE" hint='Leave blank to name it later — shows as "TBD" until then.'>
          <input
            className="input"
            type="text"
            placeholder="e.g. Ashes of the Court"
            value={sessionModal.title}
            onChange={(e) => setSessionModal({ ...sessionModal, title: e.target.value })}
          />
        </Field>
        <Field label="STATUS">
          <PillSelect
            options={["planned", "ready"] as const}
            value={sessionModal.status as "planned" | "ready"}
            onChange={(status) => setSessionModal({ ...sessionModal, status })}
          />
        </Field>
        <Field
          label="PROMISE"
          hint="One sentence. Fit Check measures the session against this."
        >
          <textarea
            className="textarea"
            placeholder="What do the players get this session, no matter what?"
            value={sessionModal.promise}
            onChange={(e) => setSessionModal({ ...sessionModal, promise: e.target.value })}
          />
        </Field>
        <div className="recap-seed-note">
          <span className="field-label">RECAP SEED</span>
          <span className="field-hint">
            Will auto-fill from Session {nextNumber - 1}'s wrap capture once it's saved.
          </span>
        </div>
      </Modal>
    );
  }

  return (
    <>
      {/* session switcher */}
      <div className="session-switcher">
        {sorted.map((s) => (
          <button
            key={s.id}
            className={`switcher-pill${active?.id === s.id ? " switcher-pill--active" : ""}`}
            onClick={() => {
              setActiveId(s.id);
              setSelectedSceneId(null);
            }}
          >
            {s.number} — {s.name || "TBD"}
          </button>
        ))}
        <button
          className="switcher-new"
          onClick={() => setSessionModal({ title: "", status: "planned", promise: "" })}
        >
          ＋ New session
        </button>
      </div>

      {active && (
        <>
          <header className="page-header">
            <div className="session-header-main">
              <span className="session-header-number">SESSION {active.number}</span>
              <h1 className="page-title">{active.name || "TBD"}</h1>
              <div className="status-pill-row">
                {SESSION_STATUSES.map((status) => (
                  <button
                    key={status}
                    className={`status-pill${active.status === status ? " status-pill--active" : ""}`}
                    onClick={() => patchStatus.mutate({ id: active.id, status })}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>
            <div className="header-actions">
              <button className="btn btn-primary" onClick={() => setWrapOpen(true)}>
                Generate recap
              </button>
            </div>
          </header>

          {/* tabs */}
          <div className="tabs">
            <button className={`tab${tab === "board" ? " tab--active" : ""}`} onClick={() => setTab("board")}>
              Scene Board
            </button>
            <button className={`tab${tab === "fit" ? " tab--active" : ""}`} onClick={() => setTab("fit")}>
              Fit Check
              {fitFlags > 0 && <span className="tab-badge">{fitFlags}</span>}
            </button>
            <button className={`tab${tab === "wrap" ? " tab--active" : ""}`} onClick={() => setTab("wrap")}>
              Wrap Capture
            </button>
          </div>

          {tab === "board" && (
            <div className="board-tab">
              {/* promise strip */}
              <div className="promise-strip">
                <div className="promise-strip-main">
                  <span className="field-label">PROMISE</span>
                  <span className="promise-text">
                    {active.promise || "No promise set for this session yet."}
                  </span>
                </div>
                <div className="promise-strip-chips">
                  {active.recap_seed && <span className="chip">recap seeded ✓</span>}
                  {fitFlags > 0 && (
                    <button className="chip chip--amber" onClick={() => setTab("fit")}>
                      fit check: {fitFlags} flag{fitFlags === 1 ? "" : "s"} →
                    </button>
                  )}
                </div>
              </div>

              <div className="board-grid">
                <section className="board-main">
                  <div className="board-toolbar">
                    <h2 className="column-heading-label">SCENE DECK</h2>
                    <div className="lens-toggle">
                      <button
                        className={`lens-option${!isAllLens ? " lens-option--active" : ""}`}
                        onClick={() => setLens("session")}
                      >
                        This session
                      </button>
                      <button
                        className={`lens-option${isAllLens ? " lens-option--active" : ""}`}
                        onClick={() => setLens("all")}
                      >
                        All scenes
                      </button>
                    </div>
                    <span className="board-hint">
                      drag between lanes · click a scene to open its editor
                    </span>
                    <button
                      className="board-new-scene"
                      onClick={() => setSceneModal({ id: null, draft: emptyDraft(active.id) })}
                    >
                      ＋ New scene
                    </button>
                  </div>

                  {isAllLens && (
                    <div className="lens-filters">
                      <span className="board-hint">Filter by session:</span>
                      {["all", ...sessionNumbers.map(String)].map((f) => (
                        <button
                          key={f}
                          className={`lens-filter${lensFilter === f ? " lens-filter--active" : ""}`}
                          onClick={() => setLensFilter(f)}
                        >
                          {f === "all" ? "All" : `S${f}`}
                        </button>
                      ))}
                    </div>
                  )}

                  <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
                    <div className="lane-board">
                      {LANES.map((lane) => (
                        <Lane
                          key={lane}
                          placement={lane}
                          scenes={lane === "ordered" ? ordered : lane === "floating" ? floating : backlog}
                          showSession={isAllLens}
                          draggable={!isAllLens}
                          onSelect={(scene) => setSelectedSceneId(scene.id)}
                        />
                      ))}
                    </div>
                  </DndContext>
                </section>

                <aside className="board-rail">
                  <div className="panel">
                    <span className="panel-label">SESSION CLUE MAP</span>
                    {clueMap.length > 0 ? (
                      <div className="clue-list">
                        {clueMap.map((clue, i) => (
                          <div className="clue-row" key={i}>
                            <TierBadge tier={clue.tier} />
                            <span className="clue-text">{clue.text}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="drawer-empty">No session-level clues mapped yet.</span>
                    )}
                    <span className="panel-footnote">
                      Per-scene clue tiers live in each scene's editor →
                    </span>
                  </div>

                  <div className="panel">
                    <span className="panel-label">RECAP SEED</span>
                    {active.recap_seed ? (
                      <>
                        <span className="panel-note">
                          Auto-filled from the previous session's wrap capture.
                        </span>
                        <p className="recap-seed-quote">"{active.recap_seed}"</p>
                      </>
                    ) : (
                      <span className="drawer-empty">
                        Fills automatically once the previous session's wrap is saved.
                      </span>
                    )}
                  </div>
                </aside>
              </div>
            </div>
          )}

          {tab === "fit" && (
            <div className="fit-tab">
              <span className="column-heading-label">
                FIT CHECK — DOES THIS SESSION FIT THE CAMPAIGN'S TONE &amp; PROMISE?
              </span>
              {fitItems.length === 0 && (
                <div className="empty-state">
                  No fit-check entries recorded for this session yet.
                </div>
              )}
              {fitItems.map((item, i) => (
                <div className={`fit-card${item.kind === "flag" ? " fit-card--flag" : ""}`} key={i}>
                  <span className={`fit-mark fit-mark--${item.kind}`}>
                    {item.kind === "flag" ? "⚑" : "✓"}
                  </span>
                  <div className="fit-card-body">
                    <span className="fit-card-title">{item.title}</span>
                    {item.note && <span className="fit-card-note">{item.note}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "wrap" && (
            <div className="wrap-tab">
              <div className="wrap-tab-header">
                <span className="column-heading-label">WRAP CAPTURE — POST-SESSION RECAP</span>
                <span className={`chip${active.status === "played" ? " chip--teal" : ""}`}>
                  {active.status === "played" ? "played" : "not yet played"}
                </span>
              </div>
              <p className="panel-note">
                Fills in after this session is marked <code className="mono-inline">played</code>.
                Feeds next session's recap seed automatically once saved.
              </p>
              <button className="btn btn-primary" style={{ width: "fit-content" }} onClick={() => setWrapOpen(true)}>
                Open full wrap capture →
              </button>
            </div>
          )}
        </>
      )}

      {/* scene detail drawer */}
      {selectedScene && !sceneModal && (
        <SceneDrawer
          scene={selectedScene}
          onClose={() => setSelectedSceneId(null)}
          onEdit={() =>
            setSceneModal({ id: selectedScene.id, draft: draftFromScene(selectedScene) })
          }
          onDelete={() => {
            setSceneModal({ id: selectedScene.id, draft: draftFromScene(selectedScene) });
            setConfirmingDelete(true);
          }}
        />
      )}

      {/* scene edit/create modal */}
      {sceneModal && (
        <Modal
          title={sceneModal.id != null ? "Edit scene" : "New scene"}
          onClose={() => {
            setSceneModal(null);
            setConfirmingDelete(false);
          }}
          footer={
            confirmingDelete ? (
              <>
                <span className="modal-danger-note">Delete this scene? This can't be undone.</span>
                <button className="btn-ghost" onClick={() => setConfirmingDelete(false)}>
                  Cancel
                </button>
                <button
                  className="btn-danger"
                  disabled={deleteScene.isPending}
                  onClick={() => {
                    if (sceneModal.id == null) return;
                    deleteScene.mutate(sceneModal.id, {
                      onSuccess: () => {
                        setSceneModal(null);
                        setConfirmingDelete(false);
                        setSelectedSceneId(null);
                      },
                    });
                  }}
                >
                  Confirm delete
                </button>
              </>
            ) : (
              <>
                {sceneModal.id != null && (
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
                    setSceneModal(null);
                    setConfirmingDelete(false);
                  }}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  disabled={createScene.isPending || patchScene.isPending}
                  onClick={saveSceneModal}
                >
                  Save
                </button>
              </>
            )
          }
        >
          <Field label="TITLE">
            <input
              className="input"
              type="text"
              value={sceneModal.draft.title}
              onChange={(e) =>
                setSceneModal({ ...sceneModal, draft: { ...sceneModal.draft, title: e.target.value } })
              }
            />
          </Field>
          <Field label="SESSION">
            <div className="pill-select">
              <button
                className={`pill-option${sceneModal.draft.session_id == null ? " pill-option--active pill-option--azure" : ""}`}
                onClick={() =>
                  setSceneModal({ ...sceneModal, draft: { ...sceneModal.draft, session_id: null } })
                }
                type="button"
              >
                none
              </button>
              {sorted.map((s) => (
                <button
                  key={s.id}
                  className={`pill-option${sceneModal.draft.session_id === s.id ? " pill-option--active pill-option--azure" : ""}`}
                  onClick={() =>
                    setSceneModal({ ...sceneModal, draft: { ...sceneModal.draft, session_id: s.id } })
                  }
                  type="button"
                >
                  {s.number}
                </button>
              ))}
            </div>
          </Field>
          <Field label="LANE">
            <PillSelect
              options={LANES}
              value={sceneModal.draft.placement}
              onChange={(placement) =>
                setSceneModal({ ...sceneModal, draft: { ...sceneModal.draft, placement } })
              }
            />
          </Field>
          <Field label="TYPE">
            <PillSelect
              options={SCENE_TYPES}
              value={sceneModal.draft.scene_type as (typeof SCENE_TYPES)[number]}
              onChange={(scene_type) =>
                setSceneModal({ ...sceneModal, draft: { ...sceneModal.draft, scene_type } })
              }
            />
          </Field>
          <Field label="SUMMARY">
            <textarea
              className="textarea"
              value={sceneModal.draft.description}
              onChange={(e) =>
                setSceneModal({
                  ...sceneModal,
                  draft: { ...sceneModal.draft, description: e.target.value },
                })
              }
            />
          </Field>
          {(
            [
              ["CORE CLUE", "core_clue"],
              ["SUPERIOR CLUE", "superior_clue"],
              ["OPTIONAL CLUE", "optional_clue"],
              ["FALSE LEAD", "false_lead"],
            ] as const
          ).map(([label, key]) => (
            <Field label={label} key={key}>
              <input
                className="input"
                type="text"
                value={sceneModal.draft[key]}
                onChange={(e) =>
                  setSceneModal({ ...sceneModal, draft: { ...sceneModal.draft, [key]: e.target.value } })
                }
              />
            </Field>
          ))}
          {(
            [
              ["IF SUCCEED", "if_succeed"],
              ["IF FAIL", "if_fail"],
              ["IF IGNORED", "if_ignore"],
              ["IF SHORT ON TIME", "if_short"],
            ] as const
          ).map(([label, key]) => (
            <Field label={label} key={key}>
              <input
                className="input"
                type="text"
                value={sceneModal.draft[key]}
                onChange={(e) =>
                  setSceneModal({ ...sceneModal, draft: { ...sceneModal.draft, [key]: e.target.value } })
                }
              />
            </Field>
          ))}
        </Modal>
      )}

      {sessionModal && renderSessionModal()}
    </>
  );
}
