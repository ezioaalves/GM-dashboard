import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest as apiFetch } from "../lib/api";
import type {
  Session,
  SessionCreate,
  SessionNote,
  SessionNotePayload,
  SessionStatus,
  SessionUpdate,
} from "../types/session";

// ── Sessions ──────────────────────────────────────────────────────────────────

export function useSessionsQuery() {
  return useQuery<Session[]>({
    queryKey: ["sessions"],
    queryFn: () => apiFetch<Session[]>("/api/sessions"),
  });
}

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation<Session, Error, SessionCreate>({
    mutationFn: (data) =>
      apiFetch<Session>("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useUpdateSession() {
  const qc = useQueryClient();
  return useMutation<Session, Error, { id: number } & SessionUpdate>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Session>(`/api/sessions/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/sessions/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function usePatchSessionStatus() {
  const qc = useQueryClient();
  return useMutation<
    { id: number; status: string },
    Error,
    { id: number; status: SessionStatus }
  >({
    mutationFn: ({ id, status }) =>
      apiFetch<{ id: number; status: string }>(`/api/sessions/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

/** Partial PATCH — only the provided fields change (promise, clue_map, wrap_capture, …). */
export function usePatchSessionFields() {
  const qc = useQueryClient();
  return useMutation<Session, Error, { id: number } & Partial<SessionUpdate>>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Session>(`/api/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

/** Bulk placement/order replace for a session's scene board. */
export function useReplaceSceneOrder() {
  const qc = useQueryClient();
  return useMutation<
    unknown,
    Error,
    {
      sessionId: number;
      ordered_scene_ids: number[];
      floating_scene_ids: number[];
      backlog_scene_ids: number[];
    }
  >({
    mutationFn: ({ sessionId, ...body }) =>
      apiFetch(`/api/sessions/${sessionId}/scene-order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scenes"] });
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

// ── Session notes (post-session recap) ───────────────────────────────────────

export function useSessionNoteQuery(sessionId: number | null) {
  return useQuery<SessionNote | null>({
    queryKey: ["session-note", sessionId],
    queryFn: () => apiFetch<SessionNote | null>(`/api/sessions/${sessionId}/note`),
    enabled: sessionId != null,
  });
}

export function useGenerateSessionNote() {
  const qc = useQueryClient();
  return useMutation<SessionNote, Error, { sessionId: number } & SessionNotePayload>({
    mutationFn: ({ sessionId, ...payload }) =>
      apiFetch<SessionNote>(`/api/sessions/${sessionId}/note/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    onSuccess: (_data, { sessionId }) =>
      qc.invalidateQueries({ queryKey: ["session-note", sessionId] }),
  });
}

export function useUpsertSessionNote() {
  const qc = useQueryClient();
  return useMutation<SessionNote, Error, { sessionId: number } & SessionNotePayload>({
    mutationFn: ({ sessionId, ...payload }) =>
      apiFetch<SessionNote>(`/api/sessions/${sessionId}/note`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    onSuccess: (_data, { sessionId }) =>
      qc.invalidateQueries({ queryKey: ["session-note", sessionId] }),
  });
}

/** Write a markdown file straight to the vault (used by the wrap "save to vault" confirm). */
export function useWriteVaultMarkdown() {
  return useMutation<unknown, Error, { path: string; content: string }>({
    mutationFn: ({ path, content }) =>
      apiFetch(`/api/files/markdown?path=${encodeURIComponent(path)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: content }),
      }),
  });
}

// Alias: usePatchSession is the full-replace PUT (same as useUpdateSession)
export function usePatchSession() {
  return useUpdateSession();
}
