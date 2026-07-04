import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Session, SessionCreate, SessionStatus, SessionUpdate } from "../types/session";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

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

// Alias: usePatchSession is the full-replace PUT (same as useUpdateSession)
export function usePatchSession() {
  return useUpdateSession();
}
