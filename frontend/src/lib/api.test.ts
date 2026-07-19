import { describe, expect, it, vi } from "vitest";
import { apiRequest } from "./api";
describe("apiRequest", () => {
  it("serializes JSON and forwards an abort signal", async () => { const signal = new AbortController().signal; const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 })); vi.stubGlobal("fetch", fetchMock); await expect(apiRequest<{ ok: boolean }>("/api/test", { method: "POST", body: { ok: true }, signal })).resolves.toEqual({ ok: true }); expect(fetchMock).toHaveBeenCalledWith("/api/test", expect.objectContaining({ signal, body: JSON.stringify({ ok: true }) })); });
  it("returns undefined for an empty successful response", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 }))); await expect(apiRequest<void>("/api/test")).resolves.toBeUndefined(); });
  it("normalizes FastAPI detail errors", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { code: "invalid_idea_transition", message: "No transition" } }), { status: 409 }))); await expect(apiRequest("/api/test")).rejects.toMatchObject({ status: 409, code: "invalid_idea_transition", message: "No transition" }); });
});
