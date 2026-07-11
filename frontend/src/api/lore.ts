import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

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

export interface LoreEntity {
  id: string;
  graph_endpoint_id: string;
  slug: string;
  title: string;
  entity_type: string;
  summary: string;
  visibility: string;
  freshness_state: string;
  review_status: string;
  source_id: string | null;
}

export interface LoreAlias {
  id: string;
  entity_id: string;
  alias: string;
}

export interface LoreSection {
  id: string;
  source_id: string;
  entity_id: string | null;
  heading: string;
  body: string;
  section_order: number;
}

export interface LoreRelationship {
  id: string;
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  unresolved_target: string;
  relationship_type: string;
  direction: "directed" | "bidirectional" | "undirected";
  provenance: string;
  context: string;
  review_status: string;
}

export interface LoreAsset {
  id: string;
  graph_endpoint_id: string;
  title: string;
  source_path: string;
  asset_type: string;
  status: string;
  mirror_state: string;
  foundry_path: string | null;
  width: number | null;
  height: number | null;
  linked_entity_id: string | null;
  usage?: string;
  freshness_state: string;
}

export interface LoreEntityDetail extends LoreEntity {
  aliases: LoreAlias[];
  sections: LoreSection[];
  relationships: LoreRelationship[];
  assets: LoreAsset[];
}

export interface LoreSource {
  id: string;
  source_path: string;
  title?: string;
  freshness_state: string;
  entity_id?: string | null;
}

export function useLoreEntitiesQuery(params?: { entity_type?: string; q?: string }) {
  const qs = params
    ? new URLSearchParams(
        Object.entries(params).filter(([, v]) => !!v) as [string, string][],
      ).toString()
    : "";
  return useQuery<LoreEntity[]>({
    queryKey: ["lore", "entities", params ?? null],
    queryFn: () => apiFetch(`/api/lore/entities${qs ? `?${qs}` : ""}`),
  });
}

export function useLoreEntityDetailQuery(id: string | null) {
  return useQuery<LoreEntityDetail>({
    queryKey: ["lore", "entities", "detail", id],
    queryFn: () => apiFetch(`/api/lore/entities/${id}`),
    enabled: !!id,
  });
}

export function useLoreSourcesQuery() {
  return useQuery<LoreSource[]>({
    queryKey: ["lore", "sources"],
    queryFn: () => apiFetch("/api/lore/sources"),
  });
}

export function useCreateLoreEntity() {
  const qc = useQueryClient();
  return useMutation<
    LoreEntity,
    Error,
    { slug: string; title: string; entity_type: string; summary?: string }
  >({
    mutationFn: (data) => jsonPost("/api/lore/entities", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lore"] }),
  });
}

export function usePatchLoreEntity() {
  const qc = useQueryClient();
  return useMutation<
    LoreEntity,
    Error,
    { id: string; title?: string; summary?: string; entity_type?: string }
  >({
    mutationFn: ({ id, ...data }) => jsonPatch(`/api/lore/entities/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lore"] }),
  });
}

export function useAddLoreAlias() {
  const qc = useQueryClient();
  return useMutation<LoreAlias, Error, { entityId: string; alias: string }>({
    mutationFn: ({ entityId, alias }) => jsonPost(`/api/lore/entities/${entityId}/aliases`, { alias }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lore"] }),
  });
}

export function useAddLoreSection() {
  const qc = useQueryClient();
  return useMutation<
    LoreSection,
    Error,
    { entityId: string; source_id: string; heading: string; body: string; section_order?: number }
  >({
    mutationFn: ({ entityId, ...data }) => jsonPost(`/api/lore/entities/${entityId}/sections`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lore"] }),
  });
}

export function usePatchLoreSection() {
  const qc = useQueryClient();
  return useMutation<
    LoreSection,
    Error,
    { id: string; heading?: string; body?: string; section_order?: number }
  >({
    mutationFn: ({ id, ...data }) => jsonPatch(`/api/lore/sections/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lore"] }),
  });
}

export function useDeleteLoreSection() {
  const qc = useQueryClient();
  return useMutation<{ deleted: boolean }, Error, string>({
    mutationFn: (id) => apiFetch(`/api/lore/sections/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lore"] }),
  });
}

export function useCreateRelationship() {
  const qc = useQueryClient();
  return useMutation<
    LoreRelationship,
    Error,
    {
      source_type: string;
      source_id: string;
      target_type: string;
      target_id?: string;
      unresolved_target?: string;
      relationship_type: string;
      direction?: string;
      provenance?: string;
    }
  >({
    mutationFn: (data) => jsonPost("/api/relationships", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lore"] }),
  });
}

// ── Assets ───────────────────────────────────────────────────────────────────

export function useAssetsQuery(params?: { asset_type?: string; mirror_state?: string; q?: string }) {
  const qs = params
    ? new URLSearchParams(
        Object.entries(params).filter(([, v]) => !!v) as [string, string][],
      ).toString()
    : "";
  return useQuery<LoreAsset[]>({
    queryKey: ["assets", params ?? null],
    queryFn: () => apiFetch(`/api/assets${qs ? `?${qs}` : ""}`),
  });
}

export function usePatchAsset() {
  const qc = useQueryClient();
  return useMutation<LoreAsset, Error, { id: string } & Record<string, unknown>>({
    mutationFn: ({ id, ...data }) => jsonPatch(`/api/assets/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });
}

// ── Vault search (unranked substring match) ──────────────────────────────────

export interface VaultSearchHit {
  path: string;
  line?: string;
  snippet?: string;
  [key: string]: unknown;
}

export function useVaultSearchQuery(q: string, limit = 20) {
  return useQuery<VaultSearchHit[]>({
    queryKey: ["vault-search", q, limit],
    queryFn: () => apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=${limit}`),
    enabled: q.trim().length >= 2,
  });
}
