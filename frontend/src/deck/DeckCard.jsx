import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";

function CardFrame({ onClick, children, className = "", as: Component = "div", isSelected = false }) {
  return (
    <Component
      type={Component === "button" ? "button" : undefined}
      className={`deck-card${className}${isSelected ? " session-card--active" : ""}`}
      onClick={onClick}
    >
      {children}
    </Component>
  );
}

function DraggableDeckCard({ id, onClick, children }) {
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

export function DeckCard({ id, onClick, children, draggable = true, as = "div", isSelected = false }) {
  if (!draggable) {
    return (
      <CardFrame onClick={onClick} as={as} isSelected={isSelected}>
        {children}
      </CardFrame>
    );
  }
  return (
    <DraggableDeckCard id={id} onClick={onClick}>
      {children}
    </DraggableDeckCard>
  );
}
