import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Thread, ThreadCreate, ThreadDetail, ThreadSummary, ThreadUpdate } from "../types/thread";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function useThreadsQuery(params?: {
  status?: string;
  arc?: string;
  priority?: string;
  freshness_state?: string;
  q?: string;
}) {
  const qs = params
    ? new URLSearchParams(
        Object.entries(params).filter(([, v]) => v != null) as [string, string][]
      ).toString()
    : "";
  return useQuery<Thread[]>({
    queryKey: ["threads", params],
    queryFn: () => apiFetch<Thread[]>(`/api/threads${qs ? `?${qs}` : ""}`),
  });
}

export function useThreadSummaryQuery() {
  return useQuery<ThreadSummary>({
    queryKey: ["threads", "summary"],
    queryFn: () => apiFetch<ThreadSummary>("/api/threads/summary"),
  });
}

export function useThreadDetailQuery(id: string | null) {
  return useQuery<ThreadDetail>({
    queryKey: ["threads", id],
    queryFn: () => apiFetch<ThreadDetail>(`/api/threads/${id}`),
    enabled: !!id,
  });
}

export function useCreateThread() {
  const qc = useQueryClient();
  return useMutation<Thread, Error, ThreadCreate>({
    mutationFn: (data) =>
      apiFetch<Thread>("/api/threads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["threads"] }),
  });
}

export function useUpdateThread() {
  const qc = useQueryClient();
  return useMutation<Thread, Error, { id: string } & ThreadUpdate>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Thread>(`/api/threads/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["threads"] }),
  });
}

export function useDeleteThread() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/threads/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["threads"] }),
  });
}
