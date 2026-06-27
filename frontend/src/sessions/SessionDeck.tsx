import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useSessionsQuery } from "../api/sessions";
import type { Session, SessionNote } from "../types/session";
import { DeckCard } from "../deck/DeckCard";
import { DeckModal } from "../deck/DeckModal";
import { SessionCard } from "./SessionCard";
import { SessionForm } from "./SessionForm";

const SESSION_STATUSES = ["Planned", "Active", "Played"] as const;
type SessionStatus = typeof SESSION_STATUSES[number];

interface SessionDeckProps {
  onStatusChange: (msg: string) => void;
  onErrorChange: (msg: string) => void;
  runAction: unknown;
  onSelectSession?: (sessionId: number) => void;
  selectedSessionId?: number | null;
}

type NoteDraft = Omit<SessionNote, "id" | "session_id"> | null;

interface SessionSaveData extends Partial<Session> {
  number: number;
  date: string | null;
  noteDraft?: NoteDraft;
}

function groupSessions(sessions: Session[]): Record<SessionStatus, Session[]> {
  const groups = Object.fromEntries(
    SESSION_STATUSES.map((status) => [status, [] as Session[]])
  ) as Record<SessionStatus, Session[]>;
  for (const session of sessions) {
    const key = SESSION_STATUSES.includes(session.status as SessionStatus)
      ? (session.status as SessionStatus)
      : "Planned";
    groups[key].push(session);
  }
  return groups;
}

function hasNoteContent(note: NoteDraft): boolean {
  if (!note) return false;
  return [
    note.next_session_hook,
    note.memory,
    note.markdown,
    note.target_path,
    ...(note.scenes || []),
    ...(note.npcs_present || []),
    ...(note.clues_discovered || []),
    ...(note.threads_touched || []),
    ...(note.unresolved_questions || []),
  ].some((value) => String(value || "").trim());
}

export default function SessionDeck({ onStatusChange, onErrorChange, runAction, onSelectSession, selectedSessionId }: SessionDeckProps) {
  const { data: sessions = [], error: queryError } = useSessionsQuery();
  const [modalSession, setModalSession] = useState<Session | Partial<Session> | null>(null);
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (queryError) {
      setError(queryError.message);
      onErrorChange(queryError.message);
    }
  }, [queryError, onErrorChange]);

  async function handleSave(data: SessionSaveData) {
    setError("");
    try {
      const isEdit = !!data.id;
      const { noteDraft, ...sessionData } = data;
      const url = isEdit ? `/api/sessions/${data.id}` : "/api/sessions";
      const res = await fetch(url, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sessionData),
      });
      if (!res.ok) throw new Error(await res.text());
      const savedSession: Session = await res.json();
      if (!isEdit && hasNoteContent(noteDraft ?? null)) {
        const noteRes = await fetch(`/api/sessions/${savedSession.id}/note/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(noteDraft),
        });
        if (!noteRes.ok) throw new Error(await noteRes.text());
      }
      setModalSession(null);
      onStatusChange(
        isEdit ? "Session updated." : hasNoteContent(noteDraft ?? null)
          ? "Session and note created."
          : "Session created."
      );
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      onErrorChange(msg);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this session? Linked scenes will move to backlog.")) return;
    setError("");
    try {
      const res = await fetch(`/api/sessions/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      setModalSession(null);
      onStatusChange("Session deleted.");
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      onErrorChange(msg);
    }
  }

  const grouped = groupSessions(sessions);

  return (
    <div className="toolPanel">
      <div className="panelHeader">
        <div>
          <h2>Session Deck</h2>
          <p>Browse sessions by status. Click a card to edit.</p>
        </div>
        <button onClick={() => setModalSession({})}>
          <Plus size={16} /> New Session
        </button>
      </div>

      {error && <p style={{ color: "#c97070", fontSize: 13, marginBottom: 8 }}>{error}</p>}

      <div className="session-deck-shell">
        {SESSION_STATUSES.map((status) => (
          <section key={status} className="deck-session-group session-status-group">
            <div className="deck-session-header">
              {status}
              <span className="deck-session-count">{grouped[status].length}</span>
            </div>
            <div className="deck-card-grid session-card-grid">
              {grouped[status].map((session) => (
                <DeckCard
                  key={session.id}
                  id={session.id}
                  as="button"
                  draggable={false}
                  isSelected={session.id === selectedSessionId}
                  onClick={() => {
                    setModalSession(session);
                    onSelectSession?.(session.id);
                  }}
                >
                  <SessionCard session={session} isSelected={session.id === selectedSessionId} />
                </DeckCard>
              ))}
            </div>
          </section>
        ))}
      </div>

      {modalSession !== null && (
        <DeckModal
          title={"id" in modalSession && modalSession.id ? `Session ${(modalSession as Session).number}` : "New Session"}
          onClose={() => setModalSession(null)}
        >
          <SessionForm
            session={modalSession as Session}
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
