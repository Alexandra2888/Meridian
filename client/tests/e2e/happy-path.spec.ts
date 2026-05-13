import { expect, test } from "@playwright/test";

/**
 * Happy-path E2E. Each `test` runs sequentially (describe.serial + workers:1)
 * and operates on a single conversation created in the first chat step, so
 * later tests reuse the DB state from earlier ones.
 *
 * The flow exercises the user journey end-to-end:
 *   1. Initial load — chrome, learner profile, empty state, sidebar.
 *   2. Send a message — assistant response streams; trace + cost/latency
 *      badges show; sidebar gains a new row.
 *   3. Reload + click the new conversation — persisted trace re-hydrates.
 *   4. Rename inline.
 *   5. Delete with inline confirm — row disappears, chat resets.
 */

// pnpm test:e2e

const STAMP = Date.now();
const UNIQUE_QUESTION = `E2E ${STAMP}: which BBA concentration fits a data analytics career?`;
const RENAMED_TITLE = `E2E ${STAMP} renamed`;

test.describe.serial("Meridian happy path", () => {
  test("loads with header, sidebar, learner card, and empty-state prompts", async ({
    page,
  }) => {
    await page.goto("/");

    // Header chrome
    await expect(page.getByText("Meridian", { exact: true })).toBeVisible();

    // Sidebar with New conversation affordance
    await expect(page.locator("aside")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "New conversation" }),
    ).toBeVisible();

    // Empty state copy + at least one canonical prompt
    await expect(
      page.getByText("One question. One coherent answer."),
    ).toBeVisible();
    await expect(
      page.getByText("What program is right for me", { exact: false }),
    ).toBeVisible();

    // CRM context card (the default learner resolves successfully). Look for
    // the badge slot specifically — "prospect" also appears in the learner
    // <select> options, which would trigger strict-mode collisions.
    await expect(
      page
        .locator("[data-slot='badge']")
        .filter({ hasText: /^prospect$/i })
        .first(),
    ).toBeVisible();
  });

  test("sends a message, streams an answer, and shows trace + cost badges", async ({
    page,
  }) => {
    await page.goto("/");

    const composer = page.locator("textarea");
    await composer.fill(UNIQUE_QUESTION);
    await page.getByRole("button", { name: "Send" }).click();

    // The user bubble shows up immediately.
    await expect(
      page.getByText(UNIQUE_QUESTION, { exact: true }),
    ).toBeVisible();

    // The trace panel only renders for assistant messages after the run
    // completes. "4 steps" = load_context + plan + an agent + synthesize.
    // Use a generous timeout because this hits a real LLM.
    await expect(page.getByText(/^\d+ steps?$/)).toBeVisible({
      timeout: 60_000,
    });

    // Composer re-enables after streaming ends.
    await expect(composer).toBeEnabled();

    // Latency + cost badges should be present (separate from the PROSPECT badge).
    const latency = page
      .locator("[data-slot='badge']")
      .filter({ hasText: /^\d+(\.\d+)?(ms|s)$/ })
      .first();
    const cost = page
      .locator("[data-slot='badge']")
      .filter({ hasText: /^\$/ })
      .first();
    await expect(latency).toBeVisible();
    await expect(cost).toBeVisible();

    // Wait briefly for the post-stream router.refresh() to surface the new
    // sidebar row, then assert it landed at the top.
    await page.waitForTimeout(800);
    const firstItem = page.locator("aside ul li").first();
    await expect(firstItem).toBeVisible();
  });

  test("persists trace + badges across reload", async ({ page }) => {
    await page.goto("/");

    // Top of the sidebar is the conversation we just created.
    const firstItem = page.locator("aside ul li").first();
    await firstItem.locator("button").first().click();

    // Wait for the message list to hydrate.
    await expect(
      page.getByText(UNIQUE_QUESTION, { exact: true }),
    ).toBeVisible();

    // Persisted trace panel + per-step labels.
    await expect(page.getByText(/^\d+ steps?$/)).toBeVisible();
    await expect(page.getByText("Loading profile from HubSpot")).toBeVisible();
    await expect(page.getByText("Synthesizing response")).toBeVisible();

    // Persisted badges (latency + cost). Match the same shape as in the
    // streaming test — values come from the DB, not the in-memory store.
    const latency = page
      .locator("[data-slot='badge']")
      .filter({ hasText: /^\d+(\.\d+)?(ms|s)$/ });
    const cost = page.locator("[data-slot='badge']").filter({ hasText: /^\$/ });
    await expect(latency.first()).toBeVisible();
    await expect(cost.first()).toBeVisible();
  });

  test("renames a conversation inline", async ({ page }) => {
    await page.goto("/");
    const firstItem = page.locator("aside ul li").first();
    await firstItem.hover();

    await firstItem
      .getByRole("button", { name: "Rename conversation" })
      .click();
    const input = firstItem.locator("input");
    await expect(input).toBeVisible();
    await input.fill(RENAMED_TITLE);
    await input.press("Enter");

    // The view-mode title button should now carry the new label.
    await expect(firstItem.locator("button").first()).toHaveText(
      RENAMED_TITLE,
      { timeout: 5_000 },
    );

    // Reload — title persisted server-side.
    await page.reload();
    await expect(
      page.locator("aside ul li").first().locator("button").first(),
    ).toHaveText(RENAMED_TITLE);
  });

  test("deletes a conversation via inline confirm", async ({ page }) => {
    await page.goto("/");

    // Locate the row by its renamed title so we don't delete an unrelated one.
    const target = page
      .locator("aside ul li")
      .filter({ hasText: RENAMED_TITLE })
      .first();
    await expect(target).toBeVisible();
    await target.hover();
    await target.getByRole("button", { name: "Delete conversation" }).click();

    // Inline confirm row replaces the item.
    await page.getByRole("button", { name: "Delete", exact: true }).click();

    // The renamed row should disappear from the sidebar.
    await expect(
      page.locator("aside ul li").filter({ hasText: RENAMED_TITLE }),
    ).toHaveCount(0, { timeout: 5_000 });
  });

  test("New conversation button resets the chat to the empty state", async ({
    page,
  }) => {
    await page.goto("/");

    // Click into any existing conversation if one is present, then click New.
    const items = page.locator("aside ul li");
    if ((await items.count()) > 0) {
      await items.first().locator("button").first().click();
      await page.waitForLoadState("networkidle");
    }

    await page.getByRole("button", { name: "New conversation" }).click();

    // URL no longer has ?conversation=
    await expect(page).toHaveURL(/^[^?]*(\?learner=[^&]+)?$/);
    // Empty-state copy is back.
    await expect(
      page.getByText("One question. One coherent answer."),
    ).toBeVisible();
  });
});

test.describe("Mobile responsiveness", () => {
  test.use({ viewport: { width: 375, height: 760 } });

  test("sidebar collapses; hamburger toggles the drawer", async ({ page }) => {
    await page.goto("/");

    const aside = page.locator("aside");
    const box = await aside.boundingBox();
    // On mobile the sidebar should be off-screen by default.
    expect(box?.x).toBeLessThan(0);

    // Hamburger opens the drawer.
    const toggle = page.getByRole("button", { name: "Open conversations" });
    await expect(toggle).toBeVisible();
    await toggle.click();

    // Wait for the transform animation to settle.
    await page.waitForTimeout(350);
    const openBox = await aside.boundingBox();
    expect(openBox?.x).toBe(0);

    // Close via the explicit close button.
    await page.getByRole("button", { name: "Close conversations" }).click();
    await page.waitForTimeout(350);
    const closedBox = await aside.boundingBox();
    expect(closedBox?.x).toBeLessThan(0);
  });
});

test.describe("Not-found route", () => {
  test("/does-not-exist returns 404 and renders the styled page", async ({
    page,
  }) => {
    const response = await page.goto("/does-not-exist");
    expect(response?.status()).toBe(404);
    await expect(page.getByText("Page not found")).toBeVisible();
    await expect(
      page.getByRole("link", { name: /Back to chat/ }),
    ).toBeVisible();
  });
});
