import { useMutation, useQueryClient } from "@tanstack/react-query";

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

type Env = "test" | "prod";

// ── NPCs — vault-owned; push is one-time & locked, refresh is review-gated ──

/** One-time, irreversible push. 409s if the NPC was ever pushed before. */
export function usePushNPCToFoundry() {
  const qc = useQueryClient();
  return useMutation<
    { pushed: boolean; env: Env; foundry_actor_id: string },
    Error,
    { slug: string; env: Env }
  >({
    mutationFn: ({ slug, env }) => jsonPost(`/api/npcs/${slug}/foundry/push`, { env }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["npcs"] }),
  });
}

/** Pull stats from Foundry; creates a pending sync review only if they differ. */
export function useRefreshNPCFromFoundry() {
  const qc = useQueryClient();
  return useMutation<
    { changed: boolean; review_id?: string },
    Error,
    { slug: string; env: Env }
  >({
    mutationFn: ({ slug, env }) => jsonPost(`/api/npcs/${slug}/foundry/refresh`, { env }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync"] }),
  });
}

/** Re-import NPCs from vault Sheet files. */
export function useSyncNPCsFromVault() {
  const qc = useQueryClient();
  return useMutation<Record<string, unknown>, Error, void>({
    mutationFn: () => jsonPost(`/api/npcs/sync`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["npcs"] }),
  });
}

// ── PCs — Foundry-owned; import-only, refresh writes directly (no review) ───

export function useRefreshPCFromFoundry() {
  const qc = useQueryClient();
  return useMutation<Record<string, unknown>, Error, { slug: string; env: Env }>({
    mutationFn: ({ slug, env }) => jsonPost(`/api/pcs/${slug}/foundry/refresh`, { env }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pcs"] }),
  });
}

export function useSyncPCsFromVault() {
  const qc = useQueryClient();
  return useMutation<Record<string, unknown>, Error, void>({
    mutationFn: () => jsonPost(`/api/pcs/sync`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pcs"] }),
  });
}
