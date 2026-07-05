import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export interface GeneratorTableEntry {
  roll: number;
  name: string;
  description: string;
}

export interface GeneratorTableData {
  key: string;
  label: string;
  die: string;
  entries: GeneratorTableEntry[];
}

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function useGeneratorTablesQuery() {
  return useQuery<GeneratorTableData[]>({
    queryKey: ["generator-tables"],
    queryFn: () => apiFetch<GeneratorTableData[]>("/api/generator/tables"),
  });
}

export function useRollGeneratorTable() {
  return useMutation<GeneratorTableEntry, Error, string>({
    mutationFn: (key) =>
      apiFetch<GeneratorTableEntry>(`/api/generator/tables/${key}/roll`, { method: "POST" }),
  });
}

export function usePatchGeneratorEntry() {
  const qc = useQueryClient();
  return useMutation<
    GeneratorTableEntry,
    Error,
    { key: string; roll: number; name?: string; description?: string }
  >({
    mutationFn: ({ key, roll, ...data }) =>
      apiFetch<GeneratorTableEntry>(`/api/generator/tables/${key}/entries/${roll}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["generator-tables"] }),
  });
}
