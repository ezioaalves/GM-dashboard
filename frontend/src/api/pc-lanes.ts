import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { PcLane, PcLaneUpsert } from "../types/pc-lane";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function usePcLanesQuery() {
  return useQuery<PcLane[]>({
    queryKey: ["pc-lanes"],
    queryFn: () => apiFetch<PcLane[]>("/api/pc-lanes"),
  });
}

export function useUpsertPcLane() {
  const qc = useQueryClient();
  return useMutation<PcLane, Error, { slug: string } & PcLaneUpsert>({
    mutationFn: ({ slug, ...data }) =>
      apiFetch<PcLane>(`/api/pcs/${slug}/lane`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pc-lanes"] }),
  });
}
