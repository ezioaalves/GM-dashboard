import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../lib/api";

export type IdeaState = "captured" | "triaged" | "promoted" | "discarded";
export type CreativeIdea = { id: string; title: string; body: string; state: IdeaState; source: string; arc_id: string | null; target: Record<string, unknown>; visibility: string; created_at: string | null };
export type IdeaInput = { title: string; body?: string; source?: string };
export type IdeaPatch = { title?: string; body?: string; state?: IdeaState };

export function useIdeasQuery(state?: IdeaState) {
  return useQuery<CreativeIdea[], ApiError>({ queryKey: ["ideas", state ?? "all"], queryFn: ({ signal }) => api.get<CreativeIdea[]>(`/api/ideas${state ? `?state=${state}` : ""}`, { signal }) });
}

export function useCreateIdea() {
  const queryClient = useQueryClient();
  return useMutation<CreativeIdea, ApiError, IdeaInput>({ mutationFn: (data) => api.post("/api/ideas", data), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ideas"] }) });
}

export function usePatchIdea() {
  const queryClient = useQueryClient();
  return useMutation<CreativeIdea, ApiError, { id: string; patch: IdeaPatch }>({ mutationFn: ({ id, patch }) => api.patch(`/api/ideas/${id}`, patch), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ideas"] }) });
}
