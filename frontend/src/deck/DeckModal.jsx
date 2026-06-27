import { X } from "lucide-react";

export function DeckModal({ title, onClose, children }) {
  return (
    <div className="modalBackdrop">
      <section className="markdownModal deck-modal">
        <header className="modalHeader">
          <div>
            <h2>{title}</h2>
          </div>
          <div className="modalActions">
            <button onClick={onClose}>
              <X size={16} /> Close
            </button>
          </div>
        </header>
        <div className="deck-modal-body">{children}</div>
      </section>
    </div>
  );
}
