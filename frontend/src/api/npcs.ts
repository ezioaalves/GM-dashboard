import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { NPC, NPCCreate, NPCUpdate, PC } from "../types/npc";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export interface NPCFilter {
  q?: string;
  affiliation?: string;
  role?: string;
  status?: string;
}

export function useNPCsQuery(filter?: NPCFilter) {
  const qs = filter
    ? new URLSearchParams(
        Object.entries(filter).filter(([, v]) => v != null) as [string, string][]
      ).toString()
    : "";
  return useQuery<NPC[]>({
    queryKey: ["npcs", filter],
    queryFn: () => apiFetch<NPC[]>(`/api/npcs${qs ? `?${qs}` : ""}`),
  });
}

export function useNPCQuery(id: number) {
  return useQuery<NPC>({
    queryKey: ["npcs", id],
    queryFn: () => apiFetch<NPC>(`/api/npcs/${id}`),
    enabled: id > 0,
  });
}

export function useCreateNPC() {
  const qc = useQueryClient();
  return useMutation<NPC, Error, NPCCreate>({
    mutationFn: (data) =>
      apiFetch<NPC>("/api/npcs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["npcs"] }),
  });
}

export function useUpdateNPC() {
  const qc = useQueryClient();
  return useMutation<NPC, Error, { id: number } & NPCUpdate>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<NPC>(`/api/npcs/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["npcs"] }),
  });
}

export function usePCsQuery() {
  return useQuery<PC[]>({
    queryKey: ["pcs"],
    queryFn: () => apiFetch<PC[]>("/api/pcs"),
  });
}

export function usePCQuery(id: number) {
  return useQuery<PC>({
    queryKey: ["pcs", id],
    queryFn: () => apiFetch<PC>(`/api/pcs/${id}`),
    enabled: id > 0,
  });
}
