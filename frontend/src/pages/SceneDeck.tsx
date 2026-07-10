import { useEffect, useMemo, useRef, useState } from "react";
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
import { SCENE_TYPES, sceneClueRows, type ClueTier, TIER_LABELS } from "../components/SceneBits";
import type { PageKey } from "../components/Sidebar";
import {
  useScenesQuery,
  useCreateScene,
  usePatchScene,
  useDeleteScene,
  useExportSceneToFoundry,
  useCaptureSceneDraft,
} from "../api/scenes";
import { useSessionsQuery, useReplaceSceneOrder } from "../api/sessions";
import { sceneToPayload } from "../lib/scene";
import type { Scene, ScenePlacement } from "../types/scene";
import type { Session } from "../types/session";

const LANES: Array<{ key: ScenePlacement; label: string; hint: string }> = [
  { key: "ordered", label: "ORDERED", hint: "the session spine" },
  { key: "floating", label: "FLOATING", hint: "slot when pacing calls" },
  { key: "backlog", label: "BACKLOG", hint: "future material" },
];

function pickActiveSession(sessions: Session[]): Session | null {
  return (
    sessions.find((s) => s.status === "ready") ??
    sessions.find((s) => s.status === "planned") ??
    [...sessions].sort((a, b) => b.number - a.number)[0] ??
    null
  );
}

function DeckCard({
  scene,
  order,
  onOpen,
}: {
  scene: Scene;
  order: number | null;
  onOpen: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: scene.id,
  });
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 5 }
    : undefined;
  const clueCount = sceneClueRows(scene).length;
  const exportLabel =
    scene.foundry_export_status === "exported"
      ? "⬆ exported"
      : scene.foundry_export_status === "failed"
        ? "⬆ failed"
        : "⬆ —";

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`deck-card${isDragging ? " scene-card--dragging" : ""}`}
      onClick={onOpen}
      {...listeners}
      {...attributes}
    >
      <div className="deck-card-top">
        {order != null && <span className="deck-card-order">{order}.</span>}
        <span className="deck-card-title">{scene.title}</span>
      </div>
      <div className="deck-card-badges">
        <span className={`type-chip type-chip--${scene.scene_type}`}>{scene.scene_type}</span>
        {scene.status === "Draft" && <span className="chip chip--amber">DRAFT</span>}
      </div>
      <div className="deck-card-meta">
        <span>◆ {clueCount} clues</span>
        <span>📎 {scene.pinned_material.length}</span>
        <span className={`deck-card-export deck-card-export--${scene.foundry_export_status}`}>
          {exportLabel}
        </span>
      </div>
    </div>
  );
}

function DeckLane({
  lane,
  scenes,
  onOpen,
}: {
  lane: (typeof LANES)[number];
  scenes: Scene[];
  onOpen: (scene: Scene) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: lane.key });
  return (
    <div ref={setNodeRef} className={`deck-lane${isOver ? " lane--over" : ""}`}>
      <div className="deck-lane-header">
        <span className="column-heading-label">{lane.label}</span>
        <span className="lane-count">{scenes.length}</span>
        <span className="deck-lane-hint">{lane.hint}</span>
      </div>
      <div className="deck-lane-cards">
        {scenes.map((scene, i) => (
          <DeckCard
            key={scene.id}
            scene={scene}
            order={lane.key === "ordered" ? i + 1 : null}
            onOpen={() => onOpen(scene)}
          />
        ))}
        {scenes.length === 0 && <div className="deck-lane-empty">drop a scene here</div>}
      </div>
    </div>
  );
}

// ── Editor drawer (autosaves) ────────────────────────────────────────────────

const TIER_FIELDS: Record<ClueTier, "core_clue" | "superior_clue" | "optional_clue" | "false_lead"> =
  {
    core: "core_clue",
    superior: "superior_clue",
    optional: "optional_clue",
    false_lead: "false_lead",
  };

function EditorDrawer({
  scene,
  onClose,
  onDeleted,
  toast,
}: {
  scene: Scene;
  onClose: () => void;
  onDeleted: () => void;
  toast: (msg: string) => void;
}) {
  const patchScene = usePatchScene();
  const deleteScene = useDeleteScene();
  const exportScene = useExportSceneToFoundry();

  const [local, setLocal] = useState<Scene>(scene);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [clueTier, setClueTier] = useState<ClueTier>("core");
  const [clueDraft, setClueDraft] = useState("");
  const [pinDraft, setPinDraft] = useState("");
  const dirty = useRef(false);

  // Re-sync local copy when a different scene is opened.
  useEffect(() => {
    setLocal(scene);
    dirty.current = false;
    setConfirmingDelete(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene.id]);

  // Debounced autosave — "changes save as you type".
  useEffect(() => {
    if (!dirty.current) return;
    const t = setTimeout(() => {
      patchScene.mutate({ id: local.id, data: sceneToPayload(local) });
      dirty.current = false;
    }, 800);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);

  function update(patch: Partial<Scene>) {
    dirty.current = true;
    setLocal((prev) => ({ ...prev, ...patch }));
  }

  const clues = sceneClueRows(local);
  const skipped = exportScene.data?.skipped_unmirrored ?? [];

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer drawer--wide">
        <div className="editor-drawer-header">
          <div className="editor-drawer-heading">
            <span className="editor-drawer-title">{local.title || "Untitled scene"}</span>
            <span className="page-subtitle">scene editor · changes save as you type</span>
          </div>
          <button className="drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="editor-drawer-body">
          <div className="drawer-section" style={{ borderTop: "none", paddingTop: 0 }}>
            <span className="drawer-section-label">BASICS</span>
            <input
              className="input"
              style={{ fontWeight: 600, fontSize: 14 }}
              type="text"
              value={local.title}
              onChange={(e) => update({ title: e.target.value })}
            />
            <Field label="SCENE TYPE">
              <PillSelect
                options={SCENE_TYPES}
                value={local.scene_type}
                onChange={(scene_type) => update({ scene_type })}
              />
            </Field>
            <Field label="PLACEMENT">
              <PillSelect
                options={["ordered", "floating", "backlog"] as const}
                value={local.placement}
                onChange={(placement) => update({ placement })}
              />
            </Field>
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">SET-UP</span>
            <textarea
              className="textarea"
              value={local.description}
              onChange={(e) => update({ description: e.target.value })}
            />
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">
              CLUES <span className="field-label-aside">— core clues are never gated behind a roll</span>
            </span>
            <div className="editor-clue-list">
              {clues.map((clue) => (
                <div className="editor-clue-row" key={clue.tier}>
                  <span className={`editor-clue-tier editor-clue-tier--${clue.tier}`}>
                    {TIER_LABELS[clue.tier]}
                  </span>
                  <span className="clue-text" style={{ flex: 1 }}>
                    {clue.text}
                  </span>
                  <button
                    className="editor-clue-remove"
                    onClick={() => update({ [TIER_FIELDS[clue.tier]]: "" } as Partial<Scene>)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
            <div className="editor-clue-add">
              <PillSelect
                options={["core", "superior", "optional", "false_lead"] as const}
                value={clueTier}
                onChange={(tier) => setClueTier(tier as ClueTier)}
                labels={{ false_lead: "false lead" }}
              />
              <input
                className="input"
                style={{ flex: 1, minWidth: 160, width: "auto" }}
                type="text"
                placeholder="New clue…"
                value={clueDraft}
                onChange={(e) => setClueDraft(e.target.value)}
              />
              <button
                className="board-new-scene"
                style={{ marginLeft: 0 }}
                onClick={() => {
                  if (!clueDraft.trim()) return;
                  update({ [TIER_FIELDS[clueTier]]: clueDraft.trim() } as Partial<Scene>);
                  setClueDraft("");
                }}
              >
                ＋ Add
              </button>
            </div>
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">BRANCHING OUTCOMES</span>
            <div className="outcome-grid">
              {(
                [
                  ["IF SUCCEED", "if_succeed", "succeed"],
                  ["IF FAIL", "if_fail", "fail"],
                  ["IF IGNORED", "if_ignore", "ignore"],
                  ["IF SHORT ON TIME", "if_short", "short"],
                ] as const
              ).map(([label, key, tone]) => (
                <div className="outcome-cell" key={key}>
                  <span className={`outcome-label branching-key--${tone}`}>{label}</span>
                  <textarea
                    className="textarea"
                    style={{ minHeight: 56 }}
                    value={local[key]}
                    onChange={(e) => update({ [key]: e.target.value } as Partial<Scene>)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">CUT / REPLACE PLAN</span>
            <textarea
              className="textarea"
              style={{ minHeight: 48 }}
              value={local.cut_or_replace_plan}
              onChange={(e) => update({ cut_or_replace_plan: e.target.value })}
            />
          </div>

          <div className="drawer-section">
            <span className="drawer-section-label">
              PINNED MATERIAL{" "}
              <span className="field-label-aside">— unmirrored assets are skipped on export</span>
            </span>
            <div className="pin-chip-row">
              {local.pinned_material.map((pin, i) => (
                <span className="pin-chip" key={`${pin.path}-${i}`}>
                  {pin.title || pin.path}
                  <button
                    className="editor-clue-remove"
                    onClick={() =>
                      update({ pinned_material: local.pinned_material.filter((_, j) => j !== i) })
                    }
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
            <div className="editor-clue-add">
              <input
                className="input"
                style={{ flex: 1, width: "auto" }}
                type="text"
                placeholder="Pin an NPC, location, asset… (vault path)"
                value={pinDraft}
                onChange={(e) => setPinDraft(e.target.value)}
              />
              <button
                className="board-new-scene"
                style={{ marginLeft: 0 }}
                onClick={() => {
                  if (!pinDraft.trim()) return;
                  update({
                    pinned_material: [
                      ...local.pinned_material,
                      { title: pinDraft.trim(), path: pinDraft.trim() },
                    ],
                  });
                  setPinDraft("");
                }}
              >
                ＋ Pin
              </button>
            </div>
          </div>

          <div className="foundry-panel">
            <span className="drawer-section-label">
              FOUNDRY JOURNAL EXPORT{" "}
              <span className="field-label-aside">
                — direct push, no review (GM-authored content going out)
              </span>
            </span>
            <div className="drawer-export-row">
              <span className={`export-badge export-badge--${local.foundry_export_status}`}>
                {local.foundry_export_status.replace("_", " ").toUpperCase()}
              </span>
              <button
                className="btn btn-primary"
                disabled={exportScene.isPending}
                onClick={() =>
                  exportScene.mutate(
                    { id: local.id },
                    {
                      onSuccess: (res) => {
                        update({ foundry_export_status: "exported" });
                        toast(
                          res.skipped_unmirrored.length > 0
                            ? `Exported to Foundry journal — ${res.skipped_unmirrored.length} unmirrored asset${res.skipped_unmirrored.length > 1 ? "s" : ""} skipped`
                            : "Exported to Foundry journal",
                        );
                      },
                      onError: (err) => toast(`Export failed: ${err.message}`),
                    },
                  )
                }
              >
                {exportScene.isPending ? "Exporting…" : "Export to Foundry"}
              </button>
            </div>
            {skipped.length > 0 && (
              <span className="drawer-warning">
                ⚠ {skipped.join(", ")} — not mirrored to Foundry; skipped on export. Mirror via
                Assets · Search.
              </span>
            )}
          </div>
        </div>

        <div className="editor-drawer-footer">
          {confirmingDelete ? (
            <>
              <span className="modal-danger-note">Delete this scene? This can't be undone.</span>
              <button className="btn-ghost" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
              <button
                className="btn-danger"
                disabled={deleteScene.isPending}
                onClick={() =>
                  deleteScene.mutate(local.id, {
                    onSuccess: () => {
                      toast("Scene deleted");
                      onDeleted();
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

// ── Page ─────────────────────────────────────────────────────────────────────

export function SceneDeck({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const { data: sessions = [] } = useSessionsQuery();
  const { data: scenes = [] } = useScenesQuery();
  const createScene = useCreateScene();
  const captureDraft = useCaptureSceneDraft();
  const replaceOrder = useReplaceSceneOrder();

  const [drawerId, setDrawerId] = useState<number | null>(null);
  const [modal, setModal] = useState<{
    mode: "structured" | "quick";
    title: string;
    scene_type: (typeof SCENE_TYPES)[number];
    placement: ScenePlacement;
    notes: string;
  } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const active = pickActiveSession(sessions);

  const pool = useMemo(() => {
    if (!active) return scenes;
    return scenes.filter(
      (s) => s.session_id === active.id || (s.placement === "backlog" && s.session_id == null),
    );
  }, [scenes, active]);

  const byLane = (lane: ScenePlacement) =>
    pool.filter((s) => s.placement === lane).sort((a, b) => a.sort_order - b.sort_order);

  const lanes: Record<ScenePlacement, Scene[]> = {
    ordered: byLane("ordered"),
    floating: byLane("floating"),
    backlog: byLane("backlog"),
  };

  const drawerScene = scenes.find((s) => s.id === drawerId) ?? null;

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }

  function handleDragEnd(event: DragEndEvent) {
    if (!active) return;
    const { active: dragged, over } = event;
    if (!over) return;
    const targetLane = over.id as ScenePlacement;
    if (!["ordered", "floating", "backlog"].includes(targetLane)) return;
    const scene = scenes.find((s) => s.id === dragged.id);
    if (!scene || scene.placement === targetLane) return;

    const without = (list: Scene[]) => list.filter((s) => s.id !== scene.id).map((s) => s.id);
    const lists: Record<ScenePlacement, number[]> = {
      ordered: without(lanes.ordered),
      floating: without(lanes.floating),
      backlog: without(lanes.backlog),
    };
    lists[targetLane].push(scene.id);

    replaceOrder.mutate({
      sessionId: active.id,
      ordered_scene_ids: lists.ordered,
      floating_scene_ids: lists.floating,
      backlog_scene_ids: lists.backlog,
    });
  }

  function saveModal() {
    if (!modal) return;
    if (!modal.title.trim()) {
      showToast("Give the scene a title first");
      return;
    }
    if (modal.mode === "quick") {
      captureDraft.mutate(
        { title: modal.title.trim(), notes: modal.notes },
        {
          onSuccess: () => {
            createScene.mutate(
              {
                title: modal.title.trim(),
                scene_type: "soft",
                status: "Draft",
                session_id: null,
                placement: "backlog",
                description: modal.notes,
              },
              {
                onSuccess: () => {
                  setModal(null);
                  showToast("Draft written to vault — added to backlog as DRAFT");
                },
              },
            );
          },
          onError: (err) => showToast(`Draft failed: ${err.message}`),
        },
      );
    } else {
      createScene.mutate(
        {
          title: modal.title.trim(),
          scene_type: modal.scene_type,
          session_id: modal.placement === "backlog" ? null : (active?.id ?? null),
          placement: modal.placement,
          description: modal.notes,
        },
        {
          onSuccess: (created) => {
            setModal(null);
            showToast("Scene created");
            setDrawerId(created.id);
          },
        },
      );
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Scene Deck</h1>
          <span className="page-subtitle">ordered · floating · backlog — drag to re-slot</span>
        </div>
        <div className="header-actions">
          <button
            className="btn-ghost"
            onClick={() =>
              setModal({ mode: "quick", title: "", scene_type: "soft", placement: "backlog", notes: "" })
            }
          >
            ✎ Quick draft
          </button>
          <button
            className="btn btn-primary"
            onClick={() =>
              setModal({
                mode: "structured",
                title: "",
                scene_type: "soft",
                placement: "floating",
                notes: "",
              })
            }
          >
            ＋ New scene
          </button>
        </div>
      </header>

      {active && (
        <div className="session-context-strip">
          <span className={`chip${active.status === "ready" ? " chip--teal" : ""}`}>
            {active.status.toUpperCase()}
          </span>
          <span className="session-context-name">
            Session {active.number} — {active.name || "TBD"}
          </span>
          <span className="board-hint">
            {LANES.map((l) => `${lanes[l.key].length} ${l.key}`).join(" / ")}
          </span>
          <button className="panel-link session-context-open" onClick={() => onNavigate("sessions")}>
            Open in Session Planner →
          </button>
        </div>
      )}

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="deck-board">
          {LANES.map((lane) => (
            <DeckLane
              key={lane.key}
              lane={lane}
              scenes={lanes[lane.key]}
              onOpen={(scene) => setDrawerId(scene.id)}
            />
          ))}
        </div>
      </DndContext>

      {drawerScene && (
        <EditorDrawer
          scene={drawerScene}
          onClose={() => setDrawerId(null)}
          onDeleted={() => setDrawerId(null)}
          toast={showToast}
        />
      )}

      {modal && (
        <Modal
          title={modal.mode === "quick" ? "Quick scene draft" : "New scene"}
          onClose={() => setModal(null)}
          footer={
            <>
              <button className="btn-ghost" onClick={() => setModal(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={createScene.isPending || captureDraft.isPending}
                onClick={saveModal}
              >
                {modal.mode === "quick" ? "Save vault draft" : "Create scene"}
              </button>
            </>
          }
        >
          <div className="tabs" style={{ marginTop: -8 }}>
            <button
              className={`tab${modal.mode === "structured" ? " tab--active" : ""}`}
              onClick={() => setModal({ ...modal, mode: "structured" })}
            >
              Structured
            </button>
            <button
              className={`tab${modal.mode === "quick" ? " tab--active" : ""}`}
              onClick={() => setModal({ ...modal, mode: "quick" })}
            >
              Quick draft
            </button>
          </div>
          <Field label="TITLE">
            <input
              className="input"
              type="text"
              value={modal.title}
              onChange={(e) => setModal({ ...modal, title: e.target.value })}
            />
          </Field>
          {modal.mode === "structured" && (
            <>
              <Field label="SCENE TYPE">
                <PillSelect
                  options={SCENE_TYPES}
                  value={modal.scene_type}
                  onChange={(scene_type) => setModal({ ...modal, scene_type })}
                />
              </Field>
              <Field label="PLACEMENT">
                <PillSelect
                  options={["ordered", "floating", "backlog"] as const}
                  value={modal.placement}
                  onChange={(placement) => setModal({ ...modal, placement })}
                />
              </Field>
            </>
          )}
          <Field label={modal.mode === "quick" ? "NOTES (freeform — becomes the draft body)" : "SET-UP"}>
            <textarea
              className="textarea"
              style={{ minHeight: 80 }}
              value={modal.notes}
              onChange={(e) => setModal({ ...modal, notes: e.target.value })}
            />
          </Field>
          {modal.mode === "quick" && (
            <div className="quick-draft-note">
              ⓘ Quick drafts write a vault markdown draft and land in the{" "}
              <strong>backlog</strong> lane flagged <span className="mono-inline">DRAFT</span> —
              open one later to promote it to a structured scene.
            </div>
          )}
        </Modal>
      )}

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
