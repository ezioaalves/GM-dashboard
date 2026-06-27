import React from "react";
import {
  DndContext,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
} from "@dnd-kit/core";
import { ChevronDown } from "lucide-react";
import { DeckCard } from "./DeckCard";

function DroppableZone({ id, className, children }) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className={`${className}${isOver ? " deck-drop-over" : ""}`}
    >
      {children}
    </div>
  );
}

function groupBySession(items, sessions) {
  const sessionMap = {};
  for (const s of sessions) {
    sessionMap[s.id] = { session: s, items: [] };
  }
  const backlog = [];
  for (const item of items) {
    if (item.session_id != null && sessionMap[item.session_id]) {
      sessionMap[item.session_id].items.push(item);
    } else {
      backlog.push(item);
    }
  }
  return {
    sessionGroups: Object.values(sessionMap),
    backlog,
  };
}

export function DeckShell({ items, sessions, renderCard, onCardClick, onDrop }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  function handleDragEnd(event) {
    const { active, over } = event;
    if (!over) return;

    let toSessionId = null;
    if (over.id !== "backlog") {
      toSessionId = parseInt(over.id.replace("session-", ""), 10);
    }
    const itemId = parseInt(active.id, 10);
    const item = items.find((i) => i.id === itemId);
    if (item && item.session_id === toSessionId) return;

    onDrop({ itemId, toSessionId });
  }

  const { sessionGroups, backlog } = groupBySession(items, sessions);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragEnd={handleDragEnd}
    >
      <div className="deck-shell">
        <div className="deck-main">
          {sessionGroups.map(({ session, items: sessionItems }) => (
            <details key={session.id} className="deck-session-group" open>
              <summary className="deck-session-header">
                <ChevronDown size={14} />
                Session {session.number}
                {session.name ? ` — ${session.name}` : ""}
                <span className="deck-session-count">{sessionItems.length}</span>
              </summary>
              <DroppableZone
                id={`session-${session.id}`}
                className="deck-card-grid"
              >
                {sessionItems.map((item) => (
                  <DeckCard
                    key={item.id}
                    id={item.id}
                    onClick={() => onCardClick(item)}
                  >
                    {renderCard(item)}
                  </DeckCard>
                ))}
              </DroppableZone>
            </details>
          ))}
        </div>

        <aside className="deck-backlog">
          <div className="deck-backlog-header">
            Backlog
            <span className="deck-session-count">{backlog.length}</span>
          </div>
          <DroppableZone id="backlog" className="deck-backlog-list">
            {backlog.map((item) => (
              <DeckCard
                key={item.id}
                id={item.id}
                onClick={() => onCardClick(item)}
              >
                {renderCard(item)}
              </DeckCard>
            ))}
          </DroppableZone>
        </aside>
      </div>
    </DndContext>
  );
}
