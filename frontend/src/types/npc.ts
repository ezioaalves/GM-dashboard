export interface NPC {
  id: number;
  slug: string;
  name: string;
  role: string | null;
  affiliation: string | null;
  location: string | null;
  status: "alive" | "dead" | "unknown" | null;
  rank: string | null;
  tags: string[];
  narrative: string | null;
  gm_secret: string | null;
  relationship_to_pcs: Record<string, string> | null;
  stats: Record<string, unknown> | null;
  img_path: string | null;
  vault_path: string | null;
  foundry_actor_id_test: string | null;
  foundry_actor_id_prod: string | null;
  foundry_sync_locked: boolean;
  foundry_last_synced_at: string | null;
  foundry_pending_import: Record<string, unknown> | null;
}

export interface PC {
  id: number;
  slug: string;
  name: string;
  player: string | null;
  level: number | null;
  classes: Array<{ name: string; level: number }> | null;
  stats: Record<string, unknown> | null;
  narrative: string | null;
  vault_path: string | null;
  img_path: string | null;
  foundry_actor_id_test: string | null;
  foundry_actor_id_prod: string | null;
  foundry_pending_import: Record<string, unknown> | null;
  foundry_last_synced_at: string | null;
}

export interface NPCCreate {
  slug: string;
  name: string;
  role?: string;
  affiliation?: string;
  location?: string;
  status?: NPC["status"];
  rank?: string;
  tags?: string[];
  narrative?: string;
  gm_secret?: string;
  relationship_to_pcs?: Record<string, string>;
  stats?: Record<string, unknown>;
  img_path?: string;
}

export type NPCUpdate = Partial<NPCCreate>;
