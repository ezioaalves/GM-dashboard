import React, { useEffect, useState, useCallback } from "react";
import {
  DndContext,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import KanbanColumn from "./KanbanColumn";
import TicketModal from "./TicketModal";

const LANES = [
  ["now", "Now"],
  ["next", "Next"],
  ["deferred", "Deferred"],
  ["done", "Done"],
];

function groupByStage(tickets) {
  const map = { now: [], next: [], deferred: [], done: [] };
  for (const t of tickets) {
    if (map[t.stage]) map[t.stage].push(t);
    else map.next.push(t);
  }
  return map;
}

export default function KanbanBoard() {
  const [tickets, setTickets] = useState([]);
  const [modalTicket, setModalTicket] = useState(null); // null=closed, {}=create, ticket=edit
  const [modalStage, setModalStage] = useState("next");
  const [error, setError] = useState("");

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const loadTickets = useCallback(async () => {
    try {
      const res = await fetch("/api/tickets");
      if (!res.ok) throw new Error(await res.text());
      setTickets(await res.json());
    } catch (e) {
      setError(`Failed to load tickets: ${e.message}`);
    }
  }, []);

  useEffect(() => { loadTickets(); }, [loadTickets]);

  async function handleDragEnd(event) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    // over.id is either a column stage (from useDroppable) or a card id
    const targetStage = LANES.find(([s]) => s === over.id)?.[0]
      || tickets.find((t) => t.id === over.id)?.stage;

    if (!targetStage) return;

    const ticket = tickets.find((t) => t.id === active.id);
    if (!ticket || ticket.stage === targetStage) return;

    // Optimistic update
    setTickets((prev) =>
      prev.map((t) => (t.id === active.id ? { ...t, stage: targetStage } : t))
    );

    try {
      const res = await fetch(`/api/tickets/${active.id}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: targetStage }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e) {
      setError(`Failed to move ticket: ${e.message}`);
      loadTickets(); // revert
    }
  }

  function openCreate(stage) {
    setModalStage(stage);
    setModalTicket({});
  }

  function openEdit(ticket) {
    setModalStage(ticket.stage);
    setModalTicket(ticket);
  }

  async function handleSave(data) {
    try {
      const isEdit = !!data.id;
      const url = isEdit ? `/api/tickets/${data.id}` : "/api/tickets";
      const method = isEdit ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(await res.text());
      setModalTicket(null);
      await loadTickets();
    } catch (e) {
      setError(`Failed to save ticket: ${e.message}`);
    }
  }

  async function handleDelete(id) {
    if (!confirm(`Delete ticket "${id}"?`)) return;
    try {
      const res = await fetch(`/api/tickets/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      setModalTicket(null);
      await loadTickets();
    } catch (e) {
      setError(`Failed to delete ticket: ${e.message}`);
    }
  }

  const columns = groupByStage(tickets);

  return (
    <div>
      {error && (
        <p style={{ color: "#e57373", fontSize: 13, marginBottom: 8 }}>{error}</p>
      )}
      <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
        <div className="kanban-board">
          {LANES.map(([stage, label]) => (
            <KanbanColumn
              key={stage}
              stage={stage}
              label={label}
              tickets={columns[stage]}
              onAdd={openCreate}
              onCardClick={openEdit}
            />
          ))}
        </div>
      </DndContext>
      {modalTicket !== null && (
        <TicketModal
          ticket={modalTicket}
          defaultStage={modalStage}
          onSave={handleSave}
          onDelete={handleDelete}
          onClose={() => setModalTicket(null)}
        />
      )}
    </div>
  );
}
