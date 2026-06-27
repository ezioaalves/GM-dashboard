import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";

export function DeckCard({ id, onClick, children }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: String(id) });
  const style = { transform: CSS.Translate.toString(transform) };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`deck-card${isDragging ? " deck-card--dragging" : ""}`}
      onClick={onClick}
      {...listeners}
      {...attributes}
    >
      {children}
    </div>
  );
}
