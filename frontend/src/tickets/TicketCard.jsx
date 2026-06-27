import React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

const AREA_COLORS = {
  foundry: "#4a8fa8",
  docs: "#7a9e7a",
  lore: "#9e7a4a",
  mechanics: "#7a4a9e",
  skills: "#9e4a7a",
  cosmetics: "#4a7a9e",
  housekeeping: "#6a6a6a",
};

const PRIORITY_DOT = {
  high: { color: "#c0392b", label: "high" },
  med: { color: "#d4a017", label: "med" },
  low: { color: "#6a6a6a", label: "low" },
};

export default function TicketCard({ ticket, onClick }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: ticket.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const areaColor = AREA_COLORS[ticket.area] || "#6a6a6a";
  const dot = PRIORITY_DOT[ticket.priority] || PRIORITY_DOT.med;

  return (
    <article
      ref={setNodeRef}
      style={style}
      className="ticket-card"
      {...attributes}
      {...listeners}
      onClick={onClick}
    >
      <div className="ticket-card-header">
        <span
          className="ticket-area-badge"
          style={{ backgroundColor: areaColor }}
        >
          {ticket.area}
        </span>
        <span
          className="ticket-priority-dot"
          title={dot.label}
          style={{ backgroundColor: dot.color }}
        />
      </div>
      <h3 className="ticket-card-title">{ticket.title}</h3>
      {ticket.next_action && (
        <p className="ticket-card-action">{ticket.next_action}</p>
      )}
    </article>
  );
}
