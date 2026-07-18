import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type CreativeIdea = { id: string; title: string; body: string; state: string; source: string; arc_id: string | null };
type IdeaInput = { title: string; body?: string; source?: string };

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export function useIdeasQuery() {
  return useQuery<CreativeIdea[]>({ queryKey: ["ideas"], queryFn: () => apiFetch("/api/ideas") });
}

export function useCreateIdea() {
  const qc = useQueryClient();
  return useMutation<CreativeIdea, Error, IdeaInput>({
    mutationFn: (data) => apiFetch("/api/ideas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ideas"] }),
  });
}
