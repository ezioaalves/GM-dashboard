import { describe, expect, it } from "vitest";
import { navGroups, pageRegistry } from "./navigation";
describe("page registry", () => { it("has a renderer and valid navigation aliases", () => { for (const [key, page] of Object.entries(pageRegistry)) { expect(page.title).not.toEqual(""); expect(page.render).toBeTypeOf("function"); for (const alias of page.nav?.aliases ?? []) expect(pageRegistry).toHaveProperty(alias); if (page.nav?.group) expect(navGroups.some((group) => group.key === page.nav?.group)).toBe(true); expect(key).not.toEqual(""); } }); });
