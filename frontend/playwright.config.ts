import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
const chrome = "C:/Program Files/Google/Chrome/Application/chrome.exe";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: "http://127.0.0.1:3100",
    channel: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: existsSync(chrome) ? { executablePath: chrome } : {},
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1080 },
      },
    },
  ],
  webServer: {
    command: "npm run dev -- --practice --test",
    cwd: "..",
    url: "http://127.0.0.1:3100",
    timeout: 120_000,
    reuseExistingServer: false,
  },
});
