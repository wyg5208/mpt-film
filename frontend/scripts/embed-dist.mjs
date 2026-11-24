// Copy the Vite build output into the FastAPI static root (resource/public)
// for Mode A single-origin self-hosting / Docker images (migration Phase 0.5 / 3.1).
import { cpSync, rmSync, mkdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const dist = resolve(here, "..", "dist");
const target = resolve(here, "..", "..", "resource", "public");

if (!existsSync(dist)) {
  console.error("dist/ not found — run `vite build` first.");
  process.exit(1);
}

mkdirSync(target, { recursive: true });
// Preserve any pre-existing brand assets in resource/public; only overlay SPA output.
cpSync(dist, target, { recursive: true, force: true });
console.log(`embedded dist -> ${target}`);
