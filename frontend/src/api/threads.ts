import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Thread, ThreadCreate, ThreadUpdate } from "../types/thread";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function useThreadsQuery(params?: { status?: string; arc?: string }) {
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
        method: "PUT",
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
