import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Session, SessionCreate, SessionUpdate, Scene } from "../types/session";

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

// ── Scenes ────────────────────────────────────────────────────────────────────

export function useScenesQuery(sessionId?: number) {
  return useQuery<Scene[]>({
    queryKey: ["scenes", sessionId ?? "all"],
    queryFn: () =>
      apiFetch<Scene[]>(
        sessionId != null ? `/api/scenes?session_id=${sessionId}` : "/api/scenes"
      ),
  });
}

export function useCreateScene() {
  const qc = useQueryClient();
  return useMutation<Scene, Error, Partial<Scene>>({
    mutationFn: (data) =>
      apiFetch<Scene>("/api/scenes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenes"] }),
  });
}

export function useUpdateScene() {
  const qc = useQueryClient();
  return useMutation<Scene, Error, { id: number } & Partial<Scene>>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Scene>(`/api/scenes/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenes"] }),
  });
}

export function useDeleteScene() {
  const qc = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/scenes/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenes"] }),
  });
}
