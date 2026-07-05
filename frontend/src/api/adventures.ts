import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  Adventure,
  AdventureCastRow,
  AdventureClockLinkRow,
  AdventureCreate,
  AdventureDetail,
  AdventureEncounterRow,
  AdventurePatch,
  AdventurePcPressureRow,
  AdventureRewardRow,
} from "../types/adventure";

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

export function useAdventuresQuery() {
  return useQuery<Adventure[]>({
    queryKey: ["adventures"],
    queryFn: () => apiFetch<Adventure[]>("/api/adventures"),
  });
}

export function useAdventureQuery(id: number | null) {
  return useQuery<AdventureDetail>({
    queryKey: ["adventures", id],
    queryFn: () => apiFetch<AdventureDetail>(`/api/adventures/${id}`),
    enabled: id !== null,
  });
}

function invalidateAdventure(qc: ReturnType<typeof useQueryClient>, id: number) {
  qc.invalidateQueries({ queryKey: ["adventures"] });
  qc.invalidateQueries({ queryKey: ["adventures", id] });
}

export function useCreateAdventure() {
  const qc = useQueryClient();
  return useMutation<Adventure, Error, AdventureCreate>({
    mutationFn: (data) => jsonPost<Adventure>("/api/adventures", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adventures"] }),
  });
}

export function usePatchAdventure() {
  const qc = useQueryClient();
  return useMutation<AdventureDetail, Error, { id: number } & AdventurePatch>({
    mutationFn: ({ id, ...data }) => jsonPatch<AdventureDetail>(`/api/adventures/${id}`, data),
    onSuccess: (_data, variables) => invalidateAdventure(qc, variables.id),
  });
}

export function useDeleteAdventure() {
  const qc = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) => apiFetch<void>(`/api/adventures/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adventures"] }),
  });
}

export function useLinkSession() {
  const qc = useQueryClient();
  return useMutation<{ linked: boolean }, Error, { adventureId: number; sessionId: number }>({
    mutationFn: ({ adventureId, sessionId }) =>
      jsonPost(`/api/adventures/${adventureId}/sessions/${sessionId}`, {}),
    onSuccess: (_data, variables) => {
      invalidateAdventure(qc, variables.adventureId);
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

export function useUnlinkSession() {
  const qc = useQueryClient();
  return useMutation<{ unlinked: boolean }, Error, { adventureId: number; sessionId: number }>({
    mutationFn: ({ adventureId, sessionId }) =>
      apiFetch(`/api/adventures/${adventureId}/sessions/${sessionId}`, { method: "DELETE" }),
    onSuccess: (_data, variables) => {
      invalidateAdventure(qc, variables.adventureId);
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

export function useApplySpinePreset() {
  const qc = useQueryClient();
  return useMutation<Adventure, Error, { id: number; preset: "six_beat" | "five_room" }>({
    mutationFn: ({ id, preset }) => jsonPost<Adventure>(`/api/adventures/${id}/apply-spine-preset`, { preset }),
    onSuccess: (_data, variables) => invalidateAdventure(qc, variables.id),
  });
}

function makeChildResourceHooks<Row, CreatePayload, PatchPayload>(segment: string) {
  const useCreate = () => {
    const qc = useQueryClient();
    return useMutation<Row, Error, { adventureId: number } & CreatePayload>({
      mutationFn: ({ adventureId, ...data }) => jsonPost<Row>(`/api/adventures/${adventureId}/${segment}`, data),
      onSuccess: (_data, variables) => invalidateAdventure(qc, variables.adventureId),
    });
  };
  const usePatch = () => {
    const qc = useQueryClient();
    return useMutation<Row, Error, { adventureId: number; rowId: number } & PatchPayload>({
      mutationFn: ({ adventureId, rowId, ...data }) =>
        jsonPatch<Row>(`/api/adventures/${adventureId}/${segment}/${rowId}`, data),
      onSuccess: (_data, variables) => invalidateAdventure(qc, variables.adventureId),
    });
  };
  const useDelete = () => {
    const qc = useQueryClient();
    return useMutation<{ deleted: boolean }, Error, { adventureId: number; rowId: number }>({
      mutationFn: ({ adventureId, rowId }) =>
        apiFetch(`/api/adventures/${adventureId}/${segment}/${rowId}`, { method: "DELETE" }),
      onSuccess: (_data, variables) => invalidateAdventure(qc, variables.adventureId),
    });
  };
  return { useCreate, usePatch, useDelete };
}

export const castHooks = makeChildResourceHooks<
  AdventureCastRow,
  { npc_id: number; role?: string; wants_now?: string; hides?: string; if_helped?: string; if_crossed?: string },
  Partial<{ npc_id: number; role: string; wants_now: string; hides: string; if_helped: string; if_crossed: string }>
>("cast");

export const rewardHooks = makeChildResourceHooks<
  AdventureRewardRow,
  { name?: string; type?: string; who_cares?: string; mechanical_note?: string; future_hook?: string },
  Partial<{ name: string; type: string; who_cares: string; mechanical_note: string; future_hook: string }>
>("rewards");

export const encounterHooks = makeChildResourceHooks<
  AdventureEncounterRow,
  { name?: string; objective?: string; opposition?: string; terrain_constraint?: string; what_changes?: string },
  Partial<{ name: string; objective: string; opposition: string; terrain_constraint: string; what_changes: string }>
>("encounters");

export const pcPressureHooks = makeChildResourceHooks<
  AdventurePcPressureRow,
  { pc_id: number; pressure?: string; growth?: string; cost?: string },
  Partial<{ pc_id: number; pressure: string; growth: string; cost: string }>
>("pc-pressure");

export const clockLinkHooks = makeChildResourceHooks<
  AdventureClockLinkRow,
  { clock_id?: string; thread_id?: string; how_it_appears?: string; advance_trigger?: string; visible_impact?: string },
  Partial<{ clock_id: string; thread_id: string; how_it_appears: string; advance_trigger: string; visible_impact: string }>
>("clock-links");
