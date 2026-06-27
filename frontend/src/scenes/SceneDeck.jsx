import React, { useEffect, useState, useCallback } from "react";
import { Plus } from "lucide-react";
import { DeckShell } from "../deck/DeckShell";
import { DeckModal } from "../deck/DeckModal";
import { SceneCard } from "./SceneCard";
import { SceneForm } from "./SceneForm";

export default function SceneDeck({ onStatusChange, onErrorChange, runAction }) {
  const [scenes, setScenes] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [modalScene, setModalScene] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [sr, ses] = await Promise.all([
        fetch("/api/scenes"),
        fetch("/api/sessions"),
      ]);
      if (!sr.ok) throw new Error(await sr.text());
      if (!ses.ok) throw new Error(await ses.text());
      setScenes(await sr.json());
      setSessions(await ses.json());
    } catch (e) {
      setError(e.message);
      onErrorChange(e.message);
    }
  }, [onErrorChange]);

  useEffect(() => { load(); }, [load]);

  async function handleDrop({ itemId, toSessionId }) {
    setScenes((prev) =>
      prev.map((s) => (s.id === itemId ? { ...s, session_id: toSessionId } : s))
    );
    try {
      const res = await fetch(`/api/scenes/${itemId}/session`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: toSessionId }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e) {
      setError(e.message);
      load();
    }
  }

  async function handleSave(data) {
    try {
      const isEdit = !!data.id;
      const url = isEdit ? `/api/scenes/${data.id}` : "/api/scenes";
      const res = await fetch(url, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(await res.text());
      setModalScene(null);
      onStatusChange(isEdit ? "Scene updated." : "Scene created.");
      await load();
    } catch (e) {
      setError(e.message);
      onErrorChange(e.message);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this scene?")) return;
    try {
      const res = await fetch(`/api/scenes/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      setModalScene(null);
      onStatusChange("Scene deleted.");
      await load();
    } catch (e) {
      setError(e.message);
      onErrorChange(e.message);
    }
  }

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

      {error && <p style={{ color: "#c97070", fontSize: 13, marginBottom: 8 }}>{error}</p>}

      <DeckShell
        items={scenes}
        sessions={sessions}
        renderCard={(scene) => <SceneCard scene={scene} />}
        onCardClick={setModalScene}
        onDrop={handleDrop}
      />

      {modalScene !== null && (
        <DeckModal
          title={modalScene.id ? (modalScene.title || "Edit Scene") : "New Scene"}
          onClose={() => setModalScene(null)}
        >
          <SceneForm
            scene={modalScene}
            sessions={sessions}
            onSave={handleSave}
            onDelete={handleDelete}
            runAction={runAction}
            onStatusChange={onStatusChange}
          />
        </DeckModal>
      )}
    </div>
  );
}
