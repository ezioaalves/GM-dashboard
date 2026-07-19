import { useQuery } from "@tanstack/react-query";
import { apiRequest as apiFetch } from "../lib/api";
import type { CockpitSession, FoundryStatus } from "../types/cockpit";
import type { ThreadSummary } from "../types/thread";

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
