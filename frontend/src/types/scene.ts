// Scene types matching scenes_router.py _scene_to_dict output (30 fields)

export interface Scene {
  id: number;
  title: string;
  type: string;
  status: "Draft" | "Ready" | "Played" | "Cut";
  session_id: number | null;
  description: string;
  location: string[];
  cast: string[];
  clock: string[];
  cuttable: boolean;
  purpose: string;
  pc_pressure: string;
  entry_pressure: string;
  exit_condition: string;
  core_clue: string;
  superior_clue: string;
  optional_clue: string;
  false_lead: string;
  opening_image: string;
  sensory_words: string;
  interactable_objects: string;
  rules_likely: string;
  foundry_needs: string;
  replacement_route: string;
  if_succeed: string;
  if_fail: string;
  if_ignore: string;
  if_short: string;
  notes: string;
  pinned_material: Array<{ title: string; path: string }>;
}

export interface SceneCreate {
  title?: string;
  type?: string;
  status?: string;
  session_id?: number | null;
  description?: string;
  location?: string[];
  cast?: string[];
  clock?: string[];
  cuttable?: boolean;
  purpose?: string;
  pc_pressure?: string;
  entry_pressure?: string;
  exit_condition?: string;
  core_clue?: string;
  superior_clue?: string;
  optional_clue?: string;
  false_lead?: string;
  opening_image?: string;
  sensory_words?: string;
  interactable_objects?: string;
  rules_likely?: string;
  foundry_needs?: string;
  replacement_route?: string;
  if_succeed?: string;
  if_fail?: string;
  if_ignore?: string;
  if_short?: string;
  notes?: string;
  pinned_material?: Array<{ title: string; path: string }>;
}

// SceneUpdate mirrors SceneCreate — both are partial; backend uses PUT (full replace)
export type SceneUpdate = SceneCreate;
