import type { Page } from "@playwright/test";

export type Idea = {
  id: string; title: string; body: string; state: string; source: string;
  arc_id: null; target: Record<string, unknown>; visibility: string; created_at: string;
};

export function idea(overrides: Partial<Idea> = {}): Idea {
  return {
    id: "idea-1", title: "A captured idea", body: "detail", state: "captured",
    source: "quick_capture", arc_id: null, target: {}, visibility: "gm",
    created_at: "2026-07-18T12:00:00Z", ...overrides,
  };
}

export type MockState = {
  ideas: Idea[];
  failPosts: number;
  failPatches: number;
  pageErrors: string[];
  unhandled: string[];
};

const EMPTY_LIST_PATHS = new Set([
  "/api/threads", "/api/pc-lanes", "/api/risks", "/api/risks/stale",
  "/api/feedback", "/api/feedback/overdue", "/api/sessions", "/api/clocks",
]);

export async function installApiMocks(page: Page, options: { ideas?: Idea[] } = {}): Promise<MockState> {
  const state: MockState = { ideas: options.ideas ?? [], failPosts: 0, failPatches: 0, pageErrors: [], unhandled: [] };
  page.on("pageerror", (error) => state.pageErrors.push(String(error)));
  // Skip the browser's own network log lines: deliberately mocked failure
  // responses (409/500) emit them even when the UI handles the error.
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource")) state.pageErrors.push(message.text());
  });

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (path === "/api/ideas" && method === "GET") return json(state.ideas);
    if (path === "/api/ideas" && method === "POST") {
      if (state.failPosts > 0) { state.failPosts -= 1; return json({ detail: { code: "capture_failed", message: "Capture failed upstream." } }, 500); }
      const body = request.postDataJSON() as Partial<Idea>;
      const created = idea({ id: `idea-${state.ideas.length + 2}`, created_at: "2026-07-18T13:00:00Z", ...body, state: "captured" });
      state.ideas = [created, ...state.ideas];
      return json(created, 201);
    }
    const patched = path.match(/^\/api\/ideas\/([^/]+)$/);
    if (patched && method === "PATCH") {
      if (state.failPatches > 0) { state.failPatches -= 1; return json({ detail: { code: "invalid_idea_transition", message: "Transition rejected upstream." } }, 409); }
      const body = request.postDataJSON() as Partial<Idea>;
      state.ideas = state.ideas.map((item) => (item.id === patched[1] ? { ...item, ...body } : item));
      return json(state.ideas.find((item) => item.id === patched[1]));
    }

    if (path === "/api/sync/freshness") return json({ state: "fresh", counts: { pending_reviews: 0, conflict_reviews: 0 }, items: [] });
    if (path === "/api/cockpit/thread-direction") return json({ stale_threads: [], next_moves: [] });
    if (path === "/api/foundry/status") return json({ state: "unconfigured" });
    if (EMPTY_LIST_PATHS.has(path)) return json([]);

    // Everything else stays intercepted so no request ever reaches the dev
    // proxy (and therefore production); record it so tests can assert the
    // mock surface stayed complete.
    state.unhandled.push(`${method} ${path}${url.search}`);
    return json({});
  });

  return state;
}

export async function openPage(page: Page, label: string) {
  await page.goto("/");
  await page.getByRole("button", { name: label }).first().evaluate((element: HTMLButtonElement) => element.click());
}
