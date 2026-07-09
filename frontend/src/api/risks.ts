import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Risk, RiskCreate, RiskPatch } from "../types/risk";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

const jsonPost = <T>(url: string, body: unknown) =>
  apiFetch<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

const jsonPatch = <T>(url: string, body: unknown) =>
  apiFetch<T>(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export function useRisksQuery(filters?: { status?: string; likelihood?: string }) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.likelihood) params.set("likelihood", filters.likelihood);
  const qs = params.toString();
  return useQuery<Risk[]>({
    queryKey: ["risks", filters ?? {}],
    queryFn: () => apiFetch<Risk[]>(`/api/risks${qs ? `?${qs}` : ""}`),
  });
}

export function useRisksStaleQuery(threshold = 3) {
  return useQuery<Risk[]>({
    queryKey: ["risks", "stale", threshold],
    queryFn: () => apiFetch<Risk[]>(`/api/risks/stale?threshold=${threshold}`),
    refetchInterval: 30_000,
  });
}

export function useCreateRisk() {
  const qc = useQueryClient();
  return useMutation<Risk, Error, RiskCreate>({
    mutationFn: (data) => jsonPost<Risk>("/api/risks", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["risks"] }),
  });
}

export function usePatchRisk() {
  const qc = useQueryClient();
  return useMutation<Risk, Error, { id: number } & RiskPatch>({
    mutationFn: ({ id, ...data }) => jsonPatch<Risk>(`/api/risks/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["risks"] }),
  });
}

export function useDeleteRisk() {
  const qc = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) => apiFetch<void>(`/api/risks/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["risks"] }),
  });
}

export function useMarkRiskReviewed() {
  const qc = useQueryClient();
  return useMutation<Risk, Error, { id: number; session_number: number }>({
    mutationFn: ({ id, session_number }) => jsonPost<Risk>(`/api/risks/${id}/mark-reviewed`, { session_number }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["risks"] }),
  });
}
