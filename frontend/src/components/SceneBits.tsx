// Scene-type + clue-tier badges shared by Session Planner, Scene Deck, and Run Mode.

export const SCENE_TYPES = [
  "hard",
  "soft",
  "spotlight",
  "bridge",
  "added",
  "cut",
  "replacement",
] as const;

export type ClueTier = "core" | "superior" | "optional" | "false_lead";

export const CLUE_TIERS: readonly ClueTier[] = ["core", "superior", "optional", "false_lead"];

export const TIER_LABELS: Record<ClueTier, string> = {
  core: "CORE",
  superior: "SUPERIOR",
  optional: "OPTIONAL",
  false_lead: "FALSE LEAD",
};

export function SceneTypeBadge({ type, dim = false }: { type: string; dim?: boolean }) {
  const key = (type || "added").toLowerCase();
  return (
    <span className={`type-badge${dim ? " type-badge--dim" : ` type-badge--${key}`}`}>
      {key.toUpperCase()}
    </span>
  );
}

export function TierBadge({ tier }: { tier: ClueTier | string }) {
  const key = (tier || "optional").toLowerCase().replace(" ", "_") as ClueTier;
  return <span className={`tier-badge tier-badge--${key}`}>{TIER_LABELS[key] ?? key.toUpperCase()}</span>;
}

/** Per-scene clue fields (core/superior/optional/false-lead) flattened to tiered rows. */
export function sceneClueRows(scene: {
  core_clue: string;
  superior_clue: string;
  optional_clue: string;
  false_lead: string;
}): Array<{ tier: ClueTier; text: string }> {
  const rows: Array<{ tier: ClueTier; text: string }> = [];
  if (scene.core_clue) rows.push({ tier: "core", text: scene.core_clue });
  if (scene.superior_clue) rows.push({ tier: "superior", text: scene.superior_clue });
  if (scene.optional_clue) rows.push({ tier: "optional", text: scene.optional_clue });
  if (scene.false_lead) rows.push({ tier: "false_lead", text: scene.false_lead });
  return rows;
}
