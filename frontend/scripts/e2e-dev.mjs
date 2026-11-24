// Run the e2e suite against the Vite dev server (HMR) instead of the built
// dist artifact (migration Phase 3.4 requires both shapes).
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

const child = spawn(
    process.execPath,
  [resolve(root, "node_modules", "@playwright", "test", "cli.js"), "test"],
  {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, PLAYWRIGHT_BASE_URL: "http://localhost:5173" },
    shell: false,
  }
);
child.on("exit", (code) => process.exit(code ?? 1));
