// One-off: verify the library pages (成片库 /videos, 素材库 /materials) on the
// real Mode A app (:8080) with real task data.
// 1) sidebar entries present
// 2) /videos renders library cards with signed video previews + download links
// 3) /materials renders the task selector + grouped artifact rows
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.VERIFY_BASE_URL || "http://localhost:8080";
const OUT = "../.verify";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

// --- /videos 成片库 ---
await page.goto(`${BASE}/videos`);
await page.waitForSelector('[data-testid="shell-nav"]');
const navTexts = await page.locator(".nav-item").allTextContents();
console.log("nav items:", navTexts.length);
console.log(
  "nav videos entry:",
  navTexts.some((s) => /成片库|Videos Library/.test(s)),
  "| nav materials entry:",
  navTexts.some((s) => /素材库|Materials Library/.test(s))
);
await page.waitForSelector(".library-page");
await page.waitForTimeout(1500); // signed URL exchange for the previews
const cards = await page.locator(".lib-card").count();
const previews = await page.locator(".lib-card video").count();
const downloads = await page.locator(".lib-card a.btn").count();
const details = await page.locator(".lib-card .lib-head button").count();
console.log("video cards:", cards, "| video previews:", previews, "| download links:", downloads, "| detail buttons:", details);
await page.screenshot({ path: `${OUT}/09-videos-library.png` });

// --- /materials 素材库 ---
await page.goto(`${BASE}/materials`);
await page.waitForSelector('[data-testid="shell-nav"]');
await page.waitForSelector('[data-testid="materials-task-select"]');
await page.waitForTimeout(1500);
const hasSelect = (await page.locator('[data-testid="materials-task-select"]').count()) > 0;
const groups = await page.locator(".file-group").count();
const rows = await page.locator(".file-row").count();
const groupTitles = await page.locator(".file-group-title").allTextContents();
console.log("task select:", hasSelect, "| groups:", groups, "| file rows:", rows);
console.log("group titles:", groupTitles.map((s) => s.trim()).join(" | "));
const previewsM = await page.locator(".file-row video, .file-row audio, .file-row img").count();
console.log("inline previews (video/audio/img):", previewsM);
const textButtons = await page.locator(".file-row button.btn").count();
console.log("text preview buttons:", textButtons);
await page.screenshot({ path: `${OUT}/10-materials-library.png`, fullPage: true });

// flip through selector options until a task with video artifacts shows up
const optionValues = await page
  .locator('[data-testid="materials-task-select"] option')
  .evaluateAll((opts) => opts.map((o) => o.getAttribute("value")));
console.log("selector options:", optionValues.length);
let videoTaskShot = false;
for (const value of optionValues.slice(0, 6)) {
  await page.selectOption('[data-testid="materials-task-select"]', value);
  await page.waitForTimeout(900);
  const videoRows = await page.locator('.file-row[data-category="video"]').count();
  if (videoRows > 0) {
    const videoEls = await page.locator('.file-row[data-category="video"] video').count();
    const srtRows = await page.locator('.file-row[data-category="subtitle"]').count();
    console.log(
      `task ${value.slice(0, 8)}: video rows ${videoRows}, video elements ${videoEls}, subtitle rows ${srtRows}`
    );
    await page.screenshot({ path: `${OUT}/11-materials-video-task.png`, fullPage: true });
    videoTaskShot = true;
    break;
  }
}
console.log("video task screenshot:", videoTaskShot);

await browser.close();
console.log("library verify done");
