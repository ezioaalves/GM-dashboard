import React from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import TicketCard from "./TicketCard";

export default function KanbanColumn({ stage, label, tickets, onAdd, onCardClick }) {
  const { setNodeRef } = useDroppable({ id: stage });

  return (
    <div className="kanban-column">
      <div className="kanban-column-header">
        <h2 className="kanban-column-title">{label} ({tickets.length})</h2>
        <button className="kanban-column-add" title="Add ticket" onClick={() => onAdd(stage)}>+</button>
      </div>
      <SortableContext
        items={tickets.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        <div ref={setNodeRef} style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
          {tickets.map((ticket) => (
            <TicketCard
              key={ticket.id}
              ticket={ticket}
              onClick={() => onCardClick(ticket)}
            />
          ))}
        </div>
      </SortableContext>
    </div>
  );
}
