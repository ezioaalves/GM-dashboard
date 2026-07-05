import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  CascadeRule,
  CascadeRuleCreate,
  CascadeRuleUpdate,
  Clock,
  ClockCreate,
  ClockDetail,
  ClockLinkRequest,
  ClockTick,
  ClockUpdate,
  DriftCheckResult,
  FireRequest,
  FireResult,
  LifecycleUpdate,
  MirrorRequest,
  MirrorReviewResult,
  TickRequest,
} from "../types/clock";

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function useClocksQuery(params?: {
  lifecycle?: string;
  kind?: string;
  linked_to?: string;
  mirrored?: boolean;
}) {
  const qs = params
    ? new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : "";
  return useQuery<Clock[]>({
    queryKey: ["clocks", params],
    queryFn: () => apiFetch<Clock[]>(`/api/clocks${qs ? `?${qs}` : ""}`),
  });
}

export function useClockDetailQuery(id: string | null) {
  return useQuery<ClockDetail>({
    queryKey: ["clocks", id],
    queryFn: () => apiFetch<ClockDetail>(`/api/clocks/${id}`),
    enabled: !!id,
  });
}

export function useClockTicksQuery(id: string | null) {
  return useQuery<ClockTick[]>({
    queryKey: ["clocks", id, "ticks"],
    queryFn: () => apiFetch<ClockTick[]>(`/api/clocks/${id}/ticks`),
    enabled: !!id,
  });
}

export function useCreateClock() {
  const qc = useQueryClient();
  return useMutation<Clock, Error, ClockCreate>({
    mutationFn: (data) =>
      apiFetch<Clock>("/api/clocks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clocks"] }),
  });
}

export function useUpdateClock() {
  const qc = useQueryClient();
  return useMutation<Clock, Error, { id: string } & ClockUpdate>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Clock>(`/api/clocks/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clocks"] }),
  });
}

export function useUpdateLifecycle() {
  const qc = useQueryClient();
  return useMutation<Clock, Error, { id: string } & LifecycleUpdate>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Clock>(`/api/clocks/${id}/lifecycle`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clocks"] }),
  });
}

export function useTickClock() {
  const qc = useQueryClient();
  return useMutation<FireResult, Error, { id: string } & TickRequest>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<FireResult>(`/api/clocks/${id}/ticks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    // A cascade fired by this tick may move any clock, not just the target —
    // invalidate the whole family rather than a single clock's cache entry.
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clocks"] }),
  });
}

export function useAddClockLink() {
  const qc = useQueryClient();
  return useMutation<{ id: string }, Error, { id: string } & ClockLinkRequest>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<{ id: string }>(`/api/clocks/${id}/links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: (_result, { id }) => {
      qc.invalidateQueries({ queryKey: ["clocks", id] });
      qc.invalidateQueries({ queryKey: ["threads"] });
    },
  });
}

export function useRemoveClockLink() {
  const qc = useQueryClient();
  return useMutation<{ deleted: boolean }, Error, { id: string; relId: string }>({
    mutationFn: ({ id, relId }) =>
      apiFetch<{ deleted: boolean }>(`/api/clocks/${id}/links/${relId}`, {
        method: "DELETE",
      }),
    onSuccess: (_result, { id }) => {
      qc.invalidateQueries({ queryKey: ["clocks", id] });
      qc.invalidateQueries({ queryKey: ["threads"] });
    },
  });
}

export function useCascadesQuery() {
  return useQuery<CascadeRule[]>({
    queryKey: ["cascades"],
    queryFn: () => apiFetch<CascadeRule[]>("/api/cascades"),
  });
}

export function useSaveCascade() {
  const qc = useQueryClient();
  return useMutation<
    CascadeRule,
    Error,
    ({ id: string } & CascadeRuleUpdate) | CascadeRuleCreate
  >({
    mutationFn: (data) =>
      "id" in data
        ? apiFetch<CascadeRule>(`/api/cascades/${data.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify((({ id: _id, ...rest }) => rest)(data)),
          })
        : apiFetch<CascadeRule>("/api/cascades", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cascades"] }),
  });
}

export function useDeleteCascade() {
  const qc = useQueryClient();
  return useMutation<{ deleted: boolean }, Error, string>({
    mutationFn: (id) =>
      apiFetch<{ deleted: boolean }>(`/api/cascades/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cascades"] }),
  });
}

export function useFireCascade() {
  const qc = useQueryClient();
  return useMutation<FireResult, Error, { id: string } & FireRequest>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<FireResult>(`/api/cascades/${id}/fire`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: (result) => {
      if (!result.dry_run) {
        qc.invalidateQueries({ queryKey: ["clocks"] });
        qc.invalidateQueries({ queryKey: ["cascades"] });
      }
    },
  });
}

// --- Mirror / drift: Tasks 9-10 have not shipped these routes yet.
// (`POST /api/clocks/{id}/mirror`, `GET /api/clocks/mirror/drift`). Hooks are
// written now per the plan's fixed contract; they cannot be exercised until
// clockworks_mirror.py + the corresponding router routes land.

export function useMirrorClock() {
  const qc = useQueryClient();
  return useMutation<MirrorReviewResult, Error, { id: string } & MirrorRequest>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<MirrorReviewResult>(`/api/clocks/${id}/mirror`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clocks"] }),
  });
}

export function useDriftCheck() {
  // Mutation, not a query: it has side effects on the server (persists
  // freshness_state/mirror_state changes) and must be GM-invoked, never
  // fired automatically on mount.
  return useMutation<DriftCheckResult, Error, { env: "test" | "prod" }>({
    mutationFn: ({ env }) =>
      apiFetch<DriftCheckResult>(`/api/clocks/mirror/drift?env=${env}`),
  });
}
