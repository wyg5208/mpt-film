import { defineConfig, devices } from "@playwright/test";

// Playwright e2e (migration Phase 3.4): runs the same smoke suite against the
// dev server and the built dist artifact (vite preview), with the real FastAPI
// backend on :8080 (Mode A single-origin via proxy).
const devMode = !!process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  reporter: [["list"]],
  use: {
    // `e2e` runs against the production shape: FastAPI serving the embedded
    // dist (Mode A single origin, so the Origin guard accepts POSTs);
    // `e2e:dev` sets PLAYWRIGHT_BASE_URL to the HMR dev server instead
    // (migration Phase 3.4: dev 与构建产物两种形态).
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:8080",
    trace: "off",
  },
  webServer: [
    {
      command: ".venv\\Scripts\\python.exe -m uvicorn app.asgi:app --host 127.0.0.1 --port 8080",
      cwd: "..",
      url: "http://localhost:8080/ping",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    ...(devMode
      ? [
          {
            command: "node node_modules/vite/bin/vite.js dev --port 5173",
            url: "http://localhost:5173",
            reuseExistingServer: true,
            timeout: 30_000,
          },
        ]
      : []),
  ],
  projects: [
    {
      name: devMode ? "dev-server" : "built-dist (mode-a single origin)",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
