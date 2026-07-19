import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest as apiFetch } from "../lib/api";
import type { SyncFreshness, SyncReview, SyncReviewGroup } from "../types/sync";

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

export function useSyncReviewsQuery(params?: { review_status?: string; review_type?: string }) {
  const qs = params
    ? new URLSearchParams(
        Object.entries(params).filter(([, v]) => v != null) as [string, string][],
      ).toString()
    : "";
  return useQuery<SyncReview[]>({
    queryKey: ["sync", "reviews", params ?? null],
    queryFn: () => apiFetch(`/api/sync/reviews${qs ? `?${qs}` : ""}`),
  });
}

export function useSyncReviewDetailQuery(id: string | null) {
  return useQuery<SyncReview & { proposed_changes?: Record<string, unknown>; decision?: Record<string, unknown> }>({
    queryKey: ["sync", "reviews", "detail", id],
    queryFn: () => apiFetch(`/api/sync/reviews/${id}`),
    enabled: !!id,
  });
}

/** Vault scans that feed the review inbox (lore + assets + sessions). */
export function useScanVault() {
  const qc = useQueryClient();
  return useMutation<{ lore: unknown; assets: unknown; sessions: unknown }, Error, void>({
    mutationFn: async () => {
      const lore = await apiFetch("/api/lore/import/scan", { method: "POST" });
      const assets = await apiFetch("/api/assets/import/scan", { method: "POST" });
      const sessions = await apiFetch("/api/sessions/import/scan", { method: "POST" });
      return { lore, assets, sessions };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync"] }),
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

export interface BulkApplyResult {
  applied: Array<{ review_id: string; review_type: string; target_id: string }>;
  failed: Array<{ review_id: string; review_type: string; target_id: string; error: string }>;
  passes: number;
}

export function useBulkApplySyncReviews() {
  const qc = useQueryClient();
  return useMutation<BulkApplyResult, Error, void>({
    mutationFn: () =>
      apiFetch("/api/sync/reviews/bulk-apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
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
