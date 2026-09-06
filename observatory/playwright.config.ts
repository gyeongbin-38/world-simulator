import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 12_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    [
      "json",
      { outputFile: "../.observatory-cache/validation/frontend-results.json" },
    ],
  ],
  use: {
    channel:
      process.env.OBSERVATORY_BROWSER_CHANNEL ??
      (process.platform === "win32" ? "msedge" : undefined),
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:8765",
    viewport: { width: 1440, height: 1050 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    permissions: ["clipboard-read", "clipboard-write"],
    reducedMotion: "reduce",
  },
});
