import { defineConfig } from "@playwright/test";

// Requires the backend running on :8000 with seeded users (python -m app.scripts.seed --demo-data).
// Credentials come from E2E_USER / E2E_PASSWORD (defaults: admin / the ADMIN_PASSWORD you seeded).
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  use: { baseURL: "http://127.0.0.1:5173", headless: true, acceptDownloads: true },
  webServer: { command: "npm run dev", url: "http://127.0.0.1:5173", reuseExistingServer: true, timeout: 60_000 },
});
