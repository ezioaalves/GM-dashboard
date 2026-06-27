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
};

export function SceneCard({ scene, onClick }: SceneCardProps) {
  const locationText = Array.isArray(scene.location)
    ? scene.location.join(", ")
    : (scene.location as string) || "";
  const rawSnippet = scene.description || scene.purpose || "";
  const snippet = rawSnippet.slice(0, 80);
  const truncated = rawSnippet.length > 80;

  return (
    <>
      <div className="deck-card-badges" onClick={onClick}>
        {scene.type && <span className="tag">{scene.type}</span>}
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
    </>
  );
}
