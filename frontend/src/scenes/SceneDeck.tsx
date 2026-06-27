import React, { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { DeckShell } from "../deck/DeckShell";
import { DeckModal } from "../deck/DeckModal";
import { SceneCard } from "./SceneCard";
import { SceneForm } from "./SceneForm";
import { useScenesQuery } from "../api/scenes";
import type { Scene } from "../types/scene";

interface Session {
  id: number;
  number: number;
  name?: string | null;
}

interface SceneDeckProps {
  selectedSessionId?: number | null;
  onSceneClick?: (sceneId: number) => void;
  onStatusChange: (msg: string) => void;
  onErrorChange: (msg: string) => void;
  runAction: (label: string, fn: () => Promise<void>) => Promise<void>;
}

export default function SceneDeck({
  selectedSessionId,
  onSceneClick,
  onStatusChange,
  onErrorChange,
  runAction,
}: SceneDeckProps) {
  const qc = useQueryClient();

  // Scenes come from React Query, filtered by selectedSessionId when provided
  const { data: scenes = [], isLoading, error: scenesError } = useScenesQuery(
    selectedSessionId ?? undefined
  );

  // Sessions are still fetched manually (no React Query hook yet)
  const [sessions, setSessions] = useState<Session[]>([]);
  const [modalScene, setModalScene] = useState<Partial<Scene> | null>(null);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    fetch("/api/sessions")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Session[]>;
      })
      .then(setSessions)
      .catch((e: Error) => {
        setLocalError(e.message);
        onErrorChange(e.message);
      });
  }, [onErrorChange]);

  // Surface React Query errors in the same error bar
  useEffect(() => {
    if (scenesError) {
      setLocalError(scenesError.message);
      onErrorChange(scenesError.message);
    }
  }, [scenesError, onErrorChange]);

  async function handleDrop({ itemId, toSessionId }: { itemId: number; toSessionId: number | null }) {
    try {
      const res = await fetch(`/api/scenes/${itemId}/session`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: toSessionId }),
      });
      if (!res.ok) throw new Error(await res.text());
      // Invalidate React Query cache so the deck re-fetches with the new session assignment
      qc.invalidateQueries({ queryKey: ["scenes"] });
    } catch (e) {
      const msg = (e as Error).message;
      setLocalError(msg);
      onErrorChange(msg);
    }
  }

  function handleSubmit(isNew: boolean) {
    setModalScene(null);
    onStatusChange(isNew ? "Scene created." : "Scene updated.");
  }

  function handleDeleted() {
    setModalScene(null);
    onStatusChange("Scene deleted.");
  }

  const displayError = localError || "";
  const isNewScene = modalScene !== null && !modalScene.id;

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>Scene Deck</h2>
          <p>Drag cards between sessions. Click a card to edit.</p>
        </div>
        <button onClick={() => setModalScene({})}>
          <Plus size={16} /> New Scene
        </button>
      </div>

      {displayError && (
        <p style={{ color: "#c97070", fontSize: 13, marginBottom: 8 }}>{displayError}</p>
      )}

      {isLoading ? (
        <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>Loading scenes…</p>
      ) : (
        <DeckShell
          items={scenes}
          sessions={sessions}
          renderCard={(scene: Scene) => (
            <SceneCard
              scene={scene}
              onClick={() => onSceneClick?.(scene.id)}
            />
          )}
          onCardClick={(scene: Scene) => setModalScene(scene)}
          onDrop={handleDrop}
        />
      )}

      {modalScene !== null && (
        <DeckModal
          title={modalScene.id ? (modalScene.title || "Edit Scene") : "New Scene"}
          onClose={() => setModalScene(null)}
        >
          <SceneForm
            scene={modalScene}
            sessions={sessions}
            onSubmit={() => handleSubmit(isNewScene)}
            onDelete={handleDeleted}
            runAction={runAction}
            onStatusChange={onStatusChange}
          />
        </DeckModal>
      )}
    </div>
  );
}
