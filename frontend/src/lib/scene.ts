import type { Scene, SceneCreate } from "../types/scene";

/** PUT /scenes/{id} is a full replace — serialize every writable field. */
export function sceneToPayload(scene: Scene): SceneCreate {
  return {
    title: scene.title,
    scene_type: scene.scene_type,
    status: scene.status,
    session_id: scene.session_id,
    placement: scene.session_id != null ? scene.placement : "backlog",
    description: scene.description,
    location: scene.location,
    cast: scene.cast,
    clock: scene.clock,
    cuttable: scene.cuttable,
    purpose: scene.purpose,
    pc_pressure: scene.pc_pressure,
    entry_pressure: scene.entry_pressure,
    exit_condition: scene.exit_condition,
    core_clue: scene.core_clue,
    superior_clue: scene.superior_clue,
    optional_clue: scene.optional_clue,
    false_lead: scene.false_lead,
    opening_image: scene.opening_image,
    sensory_words: scene.sensory_words,
    interactable_objects: scene.interactable_objects,
    rules_likely: scene.rules_likely,
    foundry_needs: scene.foundry_needs,
    cut_or_replace_plan: scene.cut_or_replace_plan,
    if_succeed: scene.if_succeed,
    if_fail: scene.if_fail,
    if_ignore: scene.if_ignore,
    if_short: scene.if_short,
    notes: scene.notes,
    planned_notes: scene.planned_notes,
    actual_notes: scene.actual_notes,
    pinned_material: scene.pinned_material,
  };
}
