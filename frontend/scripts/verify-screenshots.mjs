// Browser verification screenshots (completion audit evidence): drives the real
// Mode A app on :8080, visits every Phase 2 page, performs a live series create,
// and writes PNG proof to .verify/. Run: node scripts/verify-screenshots.mjs
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.VERIFY_BASE_URL || "http://localhost:8080";
const OUT = "../.verify";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

async function shot(name) {
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log(`captured ${name}`);
}

// force English packs for readable evidence
await page.goto(`${BASE}/`);
await page.evaluate(() => localStorage.setItem("cf_lang", "en"));

await page.goto(`${BASE}/`);
await page.waitForSelector('[data-testid="shell-nav"]');
await shot("01-generate");

await page.goto(`${BASE}/jobs`);
await page.waitForSelector(".content, [data-testid='shell-nav']");
await shot("02-tasks");

await page.goto(`${BASE}/series`);
await page.waitForSelector('[data-testid="series-list"]');
await shot("03-series-list");

// live create through the UI, then capture the detail view
const title = `verify-${Date.now()}`;
await page.getByPlaceholder("Series title").fill(title);
await page.getByRole("button", { name: "New series" }).click();
await page.waitForSelector('[data-testid="series-detail"]');
await shot("04-series-detail");
const sid = page.url().split("/").pop();

await page.goto(`${BASE}/publish`);
await page.waitForSelector('[data-testid="publish-queue"]');
await shot("05-publish");

await page.goto(`${BASE}/settings`);
await page.waitForSelector('[data-testid="settings-section-app"]');
await shot("06-settings");

// cleanup the verification series
await page.request.delete(`${BASE}/api/v1/series/${sid}`).catch(() => {});

await browser.close();
console.log("verify screenshots done");
