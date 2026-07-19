import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest as apiFetch } from "../lib/api";
import type { Scene, SceneCreate, ScenePlacement, SceneUpdate } from "../types/scene";

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

/** Move a scene between sessions/lanes (drag-and-drop). */
export function useMoveScene() {
  const qc = useQueryClient();

  return useMutation<
    Scene,
    Error,
    { id: number; session_id: number | null; placement?: ScenePlacement; sort_order?: number }
  >({
    mutationFn: ({ id, ...body }) =>
      apiFetch<Scene>(`/api/scenes/${id}/session`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scenes"] });
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

export interface SceneExportResult {
  exported: boolean;
  foundry_journal_id: string;
  skipped_unmirrored: string[];
}

export function useExportSceneToFoundry() {
  const qc = useQueryClient();

  return useMutation<SceneExportResult, Error, { id: number; env?: "test" | "prod" }>({
    mutationFn: ({ id, env = "test" }) =>
      apiFetch<SceneExportResult>(`/api/scenes/${id}/foundry/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ env }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenes"] }),
  });
}

/** Markdown-first quick-capture path — writes a vault draft file, not a DB row. */
export function useCaptureSceneDraft() {
  return useMutation<
    { id: string; markdown?: string; default_target_path?: string },
    Error,
    { title: string; type?: string; notes?: string }
  >({
    mutationFn: (body) =>
      apiFetch(`/api/capture/scene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
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
