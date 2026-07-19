import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest as apiFetch } from "../lib/api";
import type { Ticket } from "../types/ticket";

export interface TicketCreatePayload {
  title: string;
  area: string;
  priority?: string;
  status?: string;
  stage?: string;
  body?: string;
  next_action?: string;
  resume_note?: string;
  threads?: string[];
  depends_on?: string[];
  parent_id?: string | null;
}

export type TicketUpdatePayload = Required<
  Pick<TicketCreatePayload, "title" | "status" | "area" | "priority" | "stage">
> &
  Omit<TicketCreatePayload, "title" | "area"> & { resolution?: string };

export function useTicketsQuery(params?: { stage?: string; area?: string }) {
  const qs = params
    ? new URLSearchParams(
        Object.entries(params).filter(([, v]) => v != null) as [string, string][],
      ).toString()
    : "";
  return useQuery<Ticket[]>({
    queryKey: ["tickets", params ?? null],
    queryFn: () => apiFetch(`/api/tickets${qs ? `?${qs}` : ""}`),
  });
}

export function useCreateTicket() {
  const qc = useQueryClient();
  return useMutation<Ticket, Error, TicketCreatePayload>({
    mutationFn: (data) =>
      apiFetch("/api/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  });
}

export function useUpdateTicket() {
  const qc = useQueryClient();
  return useMutation<Ticket, Error, { id: string } & TicketUpdatePayload>({
    mutationFn: ({ id, ...data }) =>
      apiFetch(`/api/tickets/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  });
}

export function usePatchTicketStage() {
  const qc = useQueryClient();
  return useMutation<Ticket, Error, { id: string; stage: string }>({
    mutationFn: ({ id, stage }) =>
      apiFetch(`/api/tickets/${id}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  });
}

export function useDeleteTicket() {
  const qc = useQueryClient();
  return useMutation<{ deleted: boolean }, Error, string>({
    mutationFn: (id) => apiFetch(`/api/tickets/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  });
}

export interface TicketImportResult {
  scanned: number;
  staged: number;
  staled: number;
}

export function useImportTicketsFromVault() {
  const qc = useQueryClient();
  return useMutation<Record<string, unknown>, Error, void>({
    mutationFn: () => apiFetch("/api/tickets/import/review", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: ["sync"] });
    },
  });
}
