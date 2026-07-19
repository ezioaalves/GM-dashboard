import { expect, test } from "@playwright/test";
import { idea, installApiMocks, openPage } from "./support";

test("shows the empty state for a fresh inbox", async ({ page }) => {
  const state = await installApiMocks(page, { ideas: [] });
  await openPage(page, "Idea Inbox");
  await expect(page.getByText("No ideas match this filter.")).toBeVisible();
  await expect(page.getByRole("tab", { name: /Active/ })).toHaveAttribute("aria-selected", "true");
  expect(state.pageErrors).toEqual([]);
});

test("captures and triages an idea with mocked APIs", async ({ page }) => {
  const state = await installApiMocks(page, { ideas: [idea()] });
  await openPage(page, "Idea Inbox");
  await expect(page.getByText("A captured idea")).toBeVisible();

  await page.getByLabel("Idea title").fill("New idea");
  await page.getByRole("button", { name: "Capture idea" }).click();
  await expect(page.getByText("New idea")).toBeVisible();

  await page.getByRole("button", { name: "Triage", exact: true }).first().click();
  await expect(page.getByText("triaged")).toBeVisible();
  expect(state.pageErrors).toEqual([]);
});

test("rejects a blank capture without calling the API", async ({ page }) => {
  const state = await installApiMocks(page, { ideas: [] });
  await openPage(page, "Idea Inbox");
  await page.getByRole("button", { name: "Capture idea" }).click();
  await expect(page.getByText("Title is required.")).toBeVisible();
  expect(state.ideas).toEqual([]);
  expect(state.pageErrors).toEqual([]);
});

test("edits an idea through the modal", async ({ page }) => {
  const state = await installApiMocks(page, { ideas: [idea()] });
  await openPage(page, "Idea Inbox");
  await page.getByRole("button", { name: "Edit A captured idea" }).click();
  const dialog = page.getByRole("dialog", { name: "Edit idea" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Title").fill("Sharper title");
  await dialog.getByLabel("Detail").fill("line one\n\nline three");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Sharper title")).toBeVisible();
  expect(state.ideas[0].body).toBe("line one\n\nline three");
  expect(state.pageErrors).toEqual([]);
});

test("promotes, discards, and restores through the lifecycle filters", async ({ page }) => {
  const state = await installApiMocks(page, {
    ideas: [idea({ id: "triaged-1", title: "Ready to promote", state: "triaged" }), idea({ id: "captured-1", title: "Still captured" })],
  });
  await openPage(page, "Idea Inbox");

  await page.getByRole("button", { name: "Promote", exact: true }).click();
  await expect(page.getByText("Ready to promote")).not.toBeVisible();
  await page.getByRole("tab", { name: /Promoted/ }).click();
  await expect(page.getByText("Ready to promote")).toBeVisible();
  await expect(page.locator(".ui-status")).toHaveText("promoted");

  await page.getByRole("tab", { name: /Active/ }).click();
  await page.getByRole("button", { name: "Discard", exact: true }).click();
  await expect(page.getByText("Still captured")).not.toBeVisible();
  await page.getByRole("tab", { name: /Discarded/ }).click();
  await page.getByRole("button", { name: "Restore", exact: true }).click();
  await expect(page.getByText("Still captured")).not.toBeVisible();
  await page.getByRole("tab", { name: /Active/ }).click();
  await expect(page.getByText("Still captured")).toBeVisible();

  expect(state.ideas.find((item) => item.id === "triaged-1")?.state).toBe("promoted");
  expect(state.ideas.find((item) => item.id === "captured-1")?.state).toBe("captured");
  expect(state.pageErrors).toEqual([]);
});

test("shows an inline error for a failed transition and retries it", async ({ page }) => {
  const state = await installApiMocks(page, { ideas: [idea()] });
  state.failPatches = 1;
  await openPage(page, "Idea Inbox");

  await page.getByRole("button", { name: "Triage", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "Transition rejected upstream." });
  await expect(alert).toBeVisible();
  await alert.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText("triaged")).toBeVisible();
  expect(state.ideas[0].state).toBe("triaged");
  expect(state.pageErrors).toEqual([]);
});
