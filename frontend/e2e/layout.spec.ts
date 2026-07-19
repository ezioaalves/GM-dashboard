import { expect, test } from "@playwright/test";
import { idea, installApiMocks, openPage } from "./support";

const SAMPLE_IDEAS = [
  idea({ id: "idea-a", title: "A rumor about the Wakizashi ledger", state: "captured" }),
  idea({ id: "idea-b", title: "Bring back the harbor inspector", body: "She saw the crates.", state: "triaged" }),
];

const PAGES = ["Idea Inbox", "Campaign Health"] as const;

test.describe("visual baselines at 1440x900", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  for (const label of PAGES) {
    test(`${label} matches its baseline`, async ({ page }) => {
      const state = await installApiMocks(page, { ideas: SAMPLE_IDEAS });
      await openPage(page, label);
      await expect(page.locator("main.main")).toBeVisible();
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot(`${label.toLowerCase().replace(/ /g, "-")}-1440x900.png`, {
        maxDiffPixelRatio: 0.02,
      });
      expect(state.pageErrors).toEqual([]);
    });
  }
});

for (const viewport of [{ width: 1024, height: 768 }, { width: 1920, height: 1080 }]) {
  test.describe(`layout integrity at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport });

    for (const label of PAGES) {
      test(`${label} has no horizontal overflow or shell overlap`, async ({ page }) => {
        const state = await installApiMocks(page, { ideas: SAMPLE_IDEAS });
        await openPage(page, label);
        await expect(page.locator("main.main")).toBeVisible();
        await page.waitForLoadState("networkidle");

        const overflow = await page.evaluate(() => {
          const root = document.documentElement;
          return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth };
        });
        expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);

        const sidebar = await page.locator("nav.sidebar").boundingBox();
        const main = await page.locator("main.main").boundingBox();
        expect(sidebar).not.toBeNull();
        expect(main).not.toBeNull();
        expect(sidebar!.x + sidebar!.width).toBeLessThanOrEqual(main!.x + 1);

        expect(state.pageErrors).toEqual([]);
      });
    }
  });
}
