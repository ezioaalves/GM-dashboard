import { useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import {
  usePatchSessionFields,
  usePatchSessionStatus,
  useGenerateSessionNote,
  useUpsertSessionNote,
  useSessionNoteQuery,
  useWriteVaultMarkdown,
} from "../api/sessions";
import { useClocksQuery } from "../api/clocks";
import { usePCsQuery } from "../api/npcs";
import type { Session, WrapCapture } from "../types/session";
import type { Clock, ClockTick } from "../types/clock";

interface TickRow {
  clockName: string;
  kind: Clock["kind"];
  before: number;
  after: number;
  reason: string;
  at: string;
}

function useSessionClockTicks(session: Session, clocks: Clock[]): TickRow[] {
  const results = useQueries({
    queries: clocks.map((clock) => ({
      queryKey: ["clock-ticks", clock.id],
      queryFn: async (): Promise<ClockTick[]> => {
        const res = await fetch(`/api/clocks/${clock.id}/ticks?limit=50`);
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      },
    })),
  });

  return useMemo(() => {
    const since = session.date ? new Date(session.date) : null;
    const rows: TickRow[] = [];
    results.forEach((result, i) => {
      const clock = clocks[i];
      for (const tick of result.data ?? []) {
        if (since && new Date(tick.created_at) < since) continue;
        rows.push({
          clockName: clock.name,
          kind: clock.kind,
          before: tick.filled_before,
          after: tick.filled_after,
          reason: tick.reason,
          at: tick.created_at,
        });
      }
    });
    return rows.sort((a, b) => a.at.localeCompare(b.at));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(results.map((r) => r.dataUpdatedAt)), clocks, session.date]);
}

export function SessionWrap({ session, onBack }: { session: Session; onBack: () => void }) {
  const { data: pcs = [] } = usePCsQuery();
  const { data: clocks = [] } = useClocksQuery();
  const { data: note } = useSessionNoteQuery(session.id);

  const patchFields = usePatchSessionFields();
  const patchStatus = usePatchSessionStatus();
  const generateNote = useGenerateSessionNote();
  const upsertNote = useUpsertSessionNote();
  const writeVault = useWriteVaultMarkdown();

  const wrap = (session.wrap_capture ?? {}) as WrapCapture;
  const [whatHappened, setWhatHappened] = useState(wrap.what_happened ?? "");
  const [looseEnds, setLooseEnds] = useState(wrap.next_session_hook ?? "");
  const [highlights, setHighlights] = useState<Record<string, string>>(
    wrap.pc_highlights ?? {},
  );
  const [saved, setSaved] = useState(false);

  const ticks = useSessionClockTicks(session, clocks);
  const played = session.status === "played";
  const draft = generateNote.data ?? note ?? null;
  const hasDraft = !!draft?.markdown;

  function saveWrapCapture(onDone?: () => void) {
    const clockMovement = ticks
      .map((t) => `${t.clockName}: ${t.before} → ${t.after} — ${t.reason}`)
      .join("; ");
    patchFields.mutate(
      {
        id: session.id,
        wrap_capture: {
          ...wrap,
          what_happened: whatHappened,
          pc_highlights: highlights,
          next_session_hook: looseEnds,
          clock_movement: clockMovement,
        } as Record<string, unknown>,
      },
      { onSuccess: onDone },
    );
  }

  function generateDraft() {
    saveWrapCapture(() => {
      generateNote.mutate({
        sessionId: session.id,
        scenes: whatHappened ? whatHappened.split("\n").filter(Boolean) : [],
        npcs_present: [],
        clues_discovered: [],
        threads_touched: ticks.map((t) => `${t.clockName}: ${t.before} → ${t.after} — ${t.reason}`),
        unresolved_questions: [],
        next_session_hook: looseEnds,
        memory: Object.entries(highlights)
          .filter(([, text]) => text.trim())
          .map(([name, text]) => `${name}: ${text}`)
          .join("\n"),
        markdown: "",
        target_path: "",
        status: "draft",
      });
    });
  }

  function confirmSave() {
    if (!draft) return;
    writeVault.mutate(
      { path: draft.target_path, content: draft.markdown },
      {
        onSuccess: () => {
          setSaved(true);
          upsertNote.mutate({
            sessionId: session.id,
            scenes: draft.scenes,
            npcs_present: draft.npcs_present,
            clues_discovered: draft.clues_discovered,
            threads_touched: draft.threads_touched,
            unresolved_questions: draft.unresolved_questions,
            next_session_hook: draft.next_session_hook,
            memory: draft.memory,
            markdown: draft.markdown,
            target_path: draft.target_path,
            status: "saved",
          });
        },
      },
    );
  }

  return (
    <div className="wrap-page">
      <header className="page-header">
        <div className="session-header-main">
          <button className="wrap-back" onClick={onBack}>
            ← Session {session.number} planner
          </button>
          <h1 className="page-title">
            Session Wrap — {session.number} · {session.name || "TBD"}
          </h1>
          <span className="page-subtitle">post-session recap capture</span>
        </div>
        <div className="header-actions">
          <button
            className={played ? "btn btn-played" : "btn btn-primary"}
            disabled={patchStatus.isPending}
            onClick={() =>
              patchStatus.mutate({ id: session.id, status: played ? "ready" : "played" })
            }
          >
            {played ? "Session played ✓" : "Mark session played"}
          </button>
        </div>
      </header>

      {!played && (
        <div className="banner banner--amber">
          <span className="banner-mark">⚑</span>
          <span>
            Wrap fields unlock once this session is marked{" "}
            <code className="mono-inline">played</code>. You can still draft below — it just won't
            feed the recap seed forward yet.
          </span>
        </div>
      )}

      <div className="field">
        <span className="field-label">WHAT HAPPENED</span>
        <textarea
          className="textarea textarea--tall"
          placeholder="Freeform recap of the session's events..."
          value={whatHappened}
          onChange={(e) => setWhatHappened(e.target.value)}
        />
      </div>

      <div className="field">
        <span className="field-label">PC HIGHLIGHTS</span>
        {pcs.length === 0 && <span className="drawer-empty">No PCs imported yet.</span>}
        {pcs.map((pc) => (
          <div className="highlight-row" key={pc.slug}>
            <span className="highlight-pc">{pc.name}</span>
            <input
              className="input"
              type="text"
              placeholder="Standout moment this session..."
              value={highlights[pc.name] ?? ""}
              onChange={(e) => setHighlights({ ...highlights, [pc.name]: e.target.value })}
            />
          </div>
        ))}
      </div>

      <div className="field">
        <span className="field-label">
          CLOCKS MOVED THIS SESSION <span className="field-label-aside">(auto, from tick history)</span>
        </span>
        <div className="tick-list">
          {ticks.length === 0 && (
            <span className="drawer-empty" style={{ padding: "9px 12px" }}>
              No clock movement recorded {session.date ? "since this session's date" : "yet"}.
            </span>
          )}
          {ticks.map((tick, i) => (
            <div className="tick-row" key={i}>
              <span className="tick-clock">{tick.clockName}</span>
              <span className="tick-before">{tick.before}</span>
              <span className="tick-arrow">→</span>
              <span className={`tick-after tick-after--${tick.kind}`}>{tick.after}</span>
              <span className="tick-reason">{tick.reason}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="field">
        <span className="field-label">LOOSE ENDS FOR NEXT TIME</span>
        <textarea
          className="textarea"
          placeholder="Becomes the next session's recap seed..."
          value={looseEnds}
          onChange={(e) => setLooseEnds(e.target.value)}
        />
      </div>

      {looseEnds.trim() && (
        <div className="banner banner--teal">
          <div className="banner-body">
            <span className="banner-label">→ WILL SEED SESSION {session.number + 1}'S RECAP</span>
            <p className="banner-quote">"{looseEnds}"</p>
          </div>
        </div>
      )}

      <div className="wrap-generate">
        <div className="wrap-generate-header">
          <span className="field-label">GENERATE RECAP MARKDOWN</span>
          <span className="board-hint">
            renders the fields above into vault-ready markdown — draft only, does not write the
            vault file
          </span>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="btn btn-primary"
            disabled={generateNote.isPending || patchFields.isPending}
            onClick={generateDraft}
          >
            {hasDraft ? "Regenerate draft" : "Generate recap draft"}
          </button>
          <button
            className="btn-ghost"
            disabled={patchFields.isPending}
            onClick={() => saveWrapCapture()}
          >
            {patchFields.isPending ? "Saving…" : "Save wrap fields"}
          </button>
        </div>
        {generateNote.isError && <span className="error-state">{generateNote.error.message}</span>}

        {hasDraft && !saved && draft && (
          <div className="draft-preview">
            <div className="draft-preview-header">
              <span className="draft-preview-path">DRAFT PREVIEW · {draft.target_path}</span>
              <span className="chip chip--amber">DRAFT · NOT SAVED</span>
            </div>
            <pre className="draft-preview-md">{draft.markdown}</pre>
            <div className="draft-preview-footer">
              <button className="btn-block" style={{ flex: "none", padding: "7px 16px" }} disabled={writeVault.isPending} onClick={confirmSave}>
                {writeVault.isPending ? "Saving…" : "Save to vault (confirm)"}
              </button>
              <span className="board-hint">writes {draft.target_path} in the vault</span>
            </div>
            {writeVault.isError && <span className="error-state">{writeVault.error.message}</span>}
          </div>
        )}

        {saved && draft && (
          <div className="banner banner--teal">
            <span className="banner-mark" style={{ color: "var(--teal)" }}>✓</span>
            <span>Saved to vault — {draft.target_path}</span>
          </div>
        )}
      </div>
    </div>
  );
}
