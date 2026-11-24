/* Headless verification for the Chango unified wordmark v2 page.
   Run: node docs/chango-wordmark/verify.mjs  ->  shots/wm-*.png */
import { chromium } from "file:///D:/python_projects/moneyprintturbo/opensources/changovideo/node_modules/.pnpm/playwright-core@1.61.1/node_modules/playwright-core/index.mjs";
import { mkdirSync } from "node:fs";

const dir = "D:/python_projects/moneyprintturbo/docs/chango-wordmark/shots";
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const errors = [];
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", e => errors.push(e.message));
page.on("requestfailed", r => errors.push("REQ FAIL: " + r.url()));

await page.goto("file:///D:/python_projects/moneyprintturbo/docs/chango-wordmark/index.html");
await page.waitForTimeout(1200);

/* asset integrity */
const badImgs = await page.evaluate(() => [...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.getAttribute("src")));
console.log("broken images:", badImgs.length ? badImgs : "none");
console.log("asset rows:", await page.locator(".asset-row").count(), "| manifest entries:", await page.evaluate(() => (window.WORDMARK_MANIFEST || []).length));
console.log("hero svgs:", await page.locator("#heroStage svg").count());

await page.screenshot({ path: dir + "/wm-01-hero.png" });
for (const id of ["compare", "anatomy", "sizes", "assets"]) {
  await page.locator("#" + id).scrollIntoViewIfNeeded();
  await page.waitForTimeout(600);
  await page.locator("#" + id).screenshot({ path: `${dir}/wm-02-${id}.png` });
}

/* controls: light bg + mono + grid */
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(400);
await page.selectOption("#ctlBg", "light");
await page.waitForTimeout(300);
await page.locator("#heroStage").screenshot({ path: dir + "/wm-03-light.png" });
await page.locator("label.switch:has(#ctlMono)").click();
await page.locator("label.switch:has(#ctlGrid)").click();
await page.waitForTimeout(300);
await page.locator("#heroStage").screenshot({ path: dir + "/wm-04-light-mono-grid.png" });
await page.selectOption("#ctlBg", "deep");
await page.waitForTimeout(300);
await page.locator("#heroStage").screenshot({ path: dir + "/wm-05-deep-mono-grid.png" });
await page.click("#ctlReset");
await page.waitForTimeout(300);
console.log("reset state:", await page.evaluate(() => ({ bg: document.getElementById("ctlBg").value, w: document.getElementById("sizeVal").textContent })));

/* mobile */
await page.setViewportSize({ width: 390, height: 844 });
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(800);
await page.screenshot({ path: dir + "/wm-06-mobile-hero.png" });
await page.locator("#assets").scrollIntoViewIfNeeded();
await page.waitForTimeout(600);
await page.screenshot({ path: dir + "/wm-07-mobile-assets.png" });
console.log("mobile horizontal overflow px:", await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth));
console.log("console/page errors:", errors.length ? errors : "none");
await browser.close();