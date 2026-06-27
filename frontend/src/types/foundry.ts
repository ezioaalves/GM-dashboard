export interface FoundryDiffField {
  field: string;
  current: unknown;
  incoming: unknown;
  changed: boolean;
}

export interface FoundryDiff {
  has_pending: boolean;
  fields: FoundryDiffField[];
}

export interface FoundrySyncResult {
  ok: boolean;
  message: string;
}
