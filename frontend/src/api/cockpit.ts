import { useQuery } from "@tanstack/react-query";
import type { CockpitSession, FoundryStatus } from "../types/cockpit";
import type { ThreadSummary } from "../types/thread";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function useCockpitSessionQuery() {
  return useQuery<CockpitSession>({
    queryKey: ["cockpit", "session"],
    queryFn: () => apiFetch<CockpitSession>("/api/cockpit/session"),
  });
}

export function useCockpitThreadDirectionQuery() {
  return useQuery<ThreadSummary>({
    queryKey: ["cockpit", "thread-direction"],
    queryFn: () => apiFetch<ThreadSummary>("/api/cockpit/thread-direction"),
    refetchInterval: 30_000,
  });
}

export function useFoundryStatusQuery() {
  return useQuery<FoundryStatus>({
    queryKey: ["foundry", "status"],
    queryFn: () => apiFetch<FoundryStatus>("/api/foundry/status"),
  });
}
