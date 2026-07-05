import type { Scene } from "../types/scene";

interface SceneCardProps {
  scene: Scene;
  onClick?: () => void;
}

const STATUS_COLORS: Record<Scene["status"], string> = {
  Draft: "var(--color-text-muted)",
  Ready: "var(--color-accent)",
  Played: "var(--color-text-secondary)",
  Cut: "#c97070",
  Replaced: "#d2a45f",
};

export function SceneCard({ scene, onClick }: SceneCardProps) {
  const locationText = Array.isArray(scene.location)
    ? scene.location.join(", ")
    : (scene.location as string) || "";
  const rawSnippet = scene.description || scene.purpose || "";
  const snippet = rawSnippet.slice(0, 80);
  const truncated = rawSnippet.length > 80;
  const replacementPlan = scene.cut_or_replace_plan || scene.replacement_route || "";
  const showReplacementPlan = replacementPlan && (
    scene.status === "Replaced" ||
    scene.status === "Cut" ||
    scene.scene_type === "hard" ||
    scene.scene_type === "replacement"
  );

  return (
    <>
      <div className="deck-card-badges" onClick={onClick}>
        {(scene.type || scene.scene_type) && <span className="tag">{scene.type || scene.scene_type}</span>}
        {scene.status && (
          <span className="tag" style={{ color: STATUS_COLORS[scene.status] }}>
            {scene.status}
          </span>
        )}
      </div>
      <div className="deck-card-title">{scene.title || "Untitled"}</div>
      {locationText && (
        <div className="deck-card-location">📍 {locationText}</div>
      )}
      {snippet && (
        <div className="deck-card-snippet">
          {snippet}{truncated ? "…" : ""}
        </div>
      )}
      {showReplacementPlan && (
        <div className="deck-card-replacement">
          Replace: {replacementPlan}
        </div>
      )}
      {scene.actual_notes && (
        <div className="deck-card-actual">
          Actual: {scene.actual_notes}
        </div>
      )}
    </>
  );
}
