import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest as apiFetch } from "../lib/api";
import type { PcLane, PcLaneUpsert } from "../types/pc-lane";

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
