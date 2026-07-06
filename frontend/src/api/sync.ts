import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { SyncFreshness, SyncReview, SyncReviewGroup } from "../types/sync";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function useGroupedSyncReviewsQuery() {
  return useQuery<{ groups: SyncReviewGroup[] }>({
    queryKey: ["sync", "reviews", "grouped"],
    queryFn: () => apiFetch("/api/sync/reviews/grouped"),
  });
}

export function useSyncFreshnessQuery() {
  return useQuery<SyncFreshness>({
    queryKey: ["sync", "freshness"],
    queryFn: () => apiFetch("/api/sync/freshness"),
    refetchInterval: 30_000,
  });
}

export function useDecideSyncReview() {
  const qc = useQueryClient();
  return useMutation<SyncReview, Error, { id: string; review_status: string; decision?: Record<string, unknown> }>({
    mutationFn: ({ id, ...data }) =>
      apiFetch(`/api/sync/reviews/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sync"] });
    },
  });
}

export function useApplySyncReview() {
  const qc = useQueryClient();
  return useMutation<Record<string, unknown>, Error, string>({
    mutationFn: (id) =>
      apiFetch(`/api/sync/reviews/${id}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation: true }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sync"] });
    },
  });
}
