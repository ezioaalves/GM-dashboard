import { useState } from "react";
import { useAdventuresQuery, useCreateAdventure } from "../api/adventures";
import type { AdventureStatus } from "../types/adventure";
import AdventureCard from "./AdventureCard";
import AdventureForm from "./AdventureForm";

const STATUS_ORDER: AdventureStatus[] = ["draft", "ready", "played", "archived"];

interface Props {
  onSelectAdventure?: (id: number) => void;
}

export default function AdventureDeck({ onSelectAdventure }: Props) {
  const { data: adventures = [], isLoading } = useAdventuresQuery();
  const createAdventure = useCreateAdventure();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const select = (id: number) => {
    setSelectedId(id);
    onSelectAdventure?.(id);
  };

  const handleNewAdventure = () => {
    createAdventure.mutate({ title: "New Adventure" }, {
      onSuccess: (adventure) => select(adventure.id),
    });
  };

  if (selectedId !== null) {
    return <AdventureForm adventureId={selectedId} onBack={() => setSelectedId(null)} />;
  }

  return (
    <div className="adventure-deck-shell">
      <div className="adventure-deck-header">
        <h2>Adventure Deck</h2>
        <p className="adventure-deck-subtitle">Browse adventures by status</p>
        <button className="btn-primary" onClick={handleNewAdventure}>New Adventure</button>
      </div>
      {isLoading && <p>Loading adventures…</p>}
      {STATUS_ORDER.map((status) => {
        const group = adventures.filter((a) => a.status === status);
        if (group.length === 0) return null;
        return (
          <div key={status} className="adventure-deck-group">
            <h3>{status}</h3>
            <div className="adventure-deck-grid">
              {group.map((adventure) => (
                <AdventureCard key={adventure.id} adventure={adventure} onClick={() => select(adventure.id)} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
