import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  ActionItemCreate,
  ActionItemPatch,
  FeedbackActionItem,
  FeedbackEntry,
  FeedbackEntryCreate,
  FeedbackEntryPatch,
  FeedbackOverdueItem,
} from "../types/feedback";

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

export function useFeedbackQuery() {
  return useQuery<FeedbackEntry[]>({
    queryKey: ["feedback"],
    queryFn: () => apiFetch<FeedbackEntry[]>("/api/feedback"),
  });
}

export function useFeedbackOverdueQuery() {
  return useQuery<FeedbackOverdueItem[]>({
    queryKey: ["feedback", "overdue"],
    queryFn: () => apiFetch<FeedbackOverdueItem[]>("/api/feedback/overdue"),
    refetchInterval: 30_000,
  });
}

export function useCreateFeedbackEntry() {
  const qc = useQueryClient();
  return useMutation<FeedbackEntry, Error, FeedbackEntryCreate>({
    mutationFn: (data) => jsonPost<FeedbackEntry>("/api/feedback", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });
}

export function usePatchFeedbackEntry() {
  const qc = useQueryClient();
  return useMutation<FeedbackEntry, Error, { id: number } & FeedbackEntryPatch>({
    mutationFn: ({ id, ...data }) => jsonPatch<FeedbackEntry>(`/api/feedback/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });
}

export function useDeleteFeedbackEntry() {
  const qc = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) => apiFetch<void>(`/api/feedback/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });
}

export function useCreateActionItem() {
  const qc = useQueryClient();
  return useMutation<FeedbackActionItem, Error, { entryId: number } & ActionItemCreate>({
    mutationFn: ({ entryId, ...data }) => jsonPost<FeedbackActionItem>(`/api/feedback/${entryId}/action-items`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });
}

export function usePatchActionItem() {
  const qc = useQueryClient();
  return useMutation<FeedbackActionItem, Error, { entryId: number; itemId: number } & ActionItemPatch>({
    mutationFn: ({ entryId, itemId, ...data }) =>
      jsonPatch<FeedbackActionItem>(`/api/feedback/${entryId}/action-items/${itemId}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });
}

export function useDeleteActionItem() {
  const qc = useQueryClient();
  return useMutation<void, Error, { entryId: number; itemId: number }>({
    mutationFn: ({ entryId, itemId }) =>
      apiFetch<void>(`/api/feedback/${entryId}/action-items/${itemId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
  });
}
