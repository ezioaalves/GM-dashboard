import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { FoundryDiff, FoundrySyncResult } from "../types/foundry";
import type { NPC, PC } from "../types/npc";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── NPC sync (two-way) ────────────────────────────────────────────────────────

export function useNPCDiff(npcId: number) {
  return useQuery<FoundryDiff>({
    queryKey: ["foundry-diff", "npc", npcId],
    queryFn: () => apiFetch<FoundryDiff>(`/api/foundry/npcs/${npcId}/diff`),
    enabled: false,
  });
}

export function useFetchNPCFromFoundry() {
  const qc = useQueryClient();
  return useMutation<FoundrySyncResult, Error, number>({
    mutationFn: (id) =>
      apiFetch<FoundrySyncResult>(`/api/foundry/npcs/${id}/fetch`, { method: "POST" }),
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: ["foundry-diff", "npc", id] }),
  });
}

export function useAcceptNPCImport() {
  const qc = useQueryClient();
  return useMutation<NPC, Error, number>({
    mutationFn: (id) =>
      apiFetch<NPC>(`/api/foundry/npcs/${id}/accept`, { method: "POST" }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["npcs", id] });
      qc.invalidateQueries({ queryKey: ["foundry-diff", "npc", id] });
    },
  });
}

export function usePushNPCToFoundry() {
  return useMutation<FoundrySyncResult, Error, number>({
    mutationFn: (id) =>
      apiFetch<FoundrySyncResult>(`/api/foundry/npcs/${id}/push`, { method: "POST" }),
  });
}

// ── PC sync (downstream only) ─────────────────────────────────────────────────

export function usePCDiff(pcId: number) {
  return useQuery<FoundryDiff>({
    queryKey: ["foundry-diff", "pc", pcId],
    queryFn: () => apiFetch<FoundryDiff>(`/api/foundry/pcs/${pcId}/diff`),
    enabled: false,
  });
}

export function useFetchPCFromFoundry() {
  const qc = useQueryClient();
  return useMutation<FoundrySyncResult, Error, number>({
    mutationFn: (id) =>
      apiFetch<FoundrySyncResult>(`/api/foundry/pcs/${id}/fetch`, { method: "POST" }),
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: ["foundry-diff", "pc", id] }),
  });
}

export function useAcceptPCImport() {
  const qc = useQueryClient();
  return useMutation<PC, Error, number>({
    mutationFn: (id) =>
      apiFetch<PC>(`/api/foundry/pcs/${id}/accept`, { method: "POST" }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["pcs", id] });
      qc.invalidateQueries({ queryKey: ["foundry-diff", "pc", id] });
    },
  });
}
