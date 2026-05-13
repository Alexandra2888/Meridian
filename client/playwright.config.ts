import { defineConfig, devices } from "@playwright/test";

/**
 * Happy-path E2E suite.
 *
 * `webServer` reuses already-running dev servers when present (matches the
 * "just run it" expectation when iterating locally) and otherwise spawns
 * them. The chat path hits OpenAI through the real backend, so timeouts are
 * generous — happy-path is what we're checking, not micro-latency.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  // Chat turns hit a live LLM — keep tests sequential so parallel turns
  // don't race against the same backend / DB row ordering.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run uvicorn app.main:app --port 8000",
      cwd: "../server",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: "pnpm dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
