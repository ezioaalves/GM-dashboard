import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Scene, SceneCreate, SceneUpdate } from "../types/scene";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Scenes ────────────────────────────────────────────────────────────────────

/**
 * Fetch all scenes, optionally filtered by session.
 * QueryKey: ["scenes", sessionId] — invalidating ["scenes"] clears all scene queries.
 */
export function useScenesQuery(sessionId?: number | null) {
  const url =
    sessionId != null ? `/api/scenes?session_id=${sessionId}` : "/api/scenes";

  return useQuery<Scene[]>({
    queryKey: ["scenes", sessionId ?? null],
    queryFn: () => apiFetch<Scene[]>(url),
  });
}

export function useCreateScene() {
  const qc = useQueryClient();

  return useMutation<Scene, Error, SceneCreate>({
    mutationFn: (data) =>
      apiFetch<Scene>("/api/scenes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenes"] }),
  });
}

export function usePatchScene() {
  const qc = useQueryClient();

  return useMutation<Scene, Error, { id: number; data: SceneUpdate }>({
    mutationFn: ({ id, data }) =>
      apiFetch<Scene>(`/api/scenes/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenes"] }),
  });
}

export function useDeleteScene() {
  const qc = useQueryClient();

  return useMutation<{ deleted: boolean }, Error, number>({
    mutationFn: (sceneId) =>
      apiFetch<{ deleted: boolean }>(`/api/scenes/${sceneId}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenes"] }),
  });
}
