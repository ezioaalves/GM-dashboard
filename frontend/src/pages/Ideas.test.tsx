import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Ideas } from "./Ideas";

let ideas = [{ id: "one", title: "Captured idea", body: "detail", state: "captured", source: "quick_capture", arc_id: null, target: {}, visibility: "gm", created_at: "2026-07-18T12:00:00Z" }];
function renderIdeas() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<QueryClientProvider client={client}><Ideas /></QueryClientProvider>); }

beforeEach(() => {
  ideas = [{ id: "one", title: "Captured idea", body: "detail", state: "captured", source: "quick_capture", arc_id: null, target: {}, visibility: "gm", created_at: "2026-07-18T12:00:00Z" }];
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (input === "/api/ideas" && method === "GET") return new Response(JSON.stringify(ideas), { status: 200 });
    if (input === "/api/ideas" && method === "POST") { const body = JSON.parse(String(init?.body)); const idea = { ...ideas[0], id: "two", ...body, state: "captured", created_at: "2026-07-18T13:00:00Z" }; ideas = [idea, ...ideas]; return new Response(JSON.stringify(idea), { status: 201 }); }
    const match = input.match(/^\/api\/ideas\/(.+)$/);
    if (match && method === "PATCH") { const patch = JSON.parse(String(init?.body)); ideas = ideas.map((idea) => idea.id === match[1] ? { ...idea, ...patch } : idea); return new Response(JSON.stringify(ideas.find((idea) => idea.id === match[1])), { status: 200 }); }
    return new Response(JSON.stringify({ detail: "Unhandled" }), { status: 404 });
  }));
});

describe("Idea Inbox", () => {
  it("validates capture, filters active ideas, and transitions lifecycle actions", async () => {
    const user = userEvent.setup(); renderIdeas(); await screen.findByText("Captured idea");
    await user.click(screen.getByRole("button", { name: "Capture idea" })); expect(screen.getByText("Title is required.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Idea title"), "New idea"); await user.click(screen.getByRole("button", { name: "Capture idea" })); await screen.findByText("New idea");
    await user.click(screen.getAllByRole("button", { name: "Triage" })[0]); await waitFor(() => expect(screen.getByText("triaged")).toBeInTheDocument());
    await user.click(screen.getByRole("tab", { name: /Promoted/ })); expect(screen.getByText("No ideas match this filter.")).toBeInTheDocument();
  });
});
