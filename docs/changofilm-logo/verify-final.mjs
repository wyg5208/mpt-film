/* Headless verification for the ChangoFilm final brand page.
   Run: node docs/changofilm-logo/verify-final.mjs  ->  shots/final-*.png */
import { chromium } from "file:///D:/python_projects/moneyprintturbo/opensources/changovideo/node_modules/.pnpm/playwright-core@1.61.1/node_modules/playwright-core/index.mjs";
import { mkdirSync } from "node:fs";

const dir = "D:/python_projects/moneyprintturbo/docs/changofilm-logo/shots";
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const errors = [];
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", e => errors.push(e.message));
page.on("requestfailed", r => errors.push("REQ FAIL: " + r.url()));

await page.goto("file:///D:/python_projects/moneyprintturbo/docs/changofilm-logo/final.html");
await page.waitForTimeout(1400);

/* asset integrity: every <img> must actually load */
const badImgs = await page.evaluate(() => [...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.getAttribute("src")));
console.log("broken images:", badImgs.length ? badImgs : "none");
console.log("asset rows:", await page.locator(".asset-row").count(), "| manifest entries:", await page.evaluate(() => (window.BRAND_MANIFEST || []).length));

/* motion actually running on hero blades */
const anim = await page.evaluate(() => getComputedStyle(document.querySelector("#heroBox .blade")).animationName);
console.log("hero blade animation:", anim);

await page.screenshot({ path: dir + "/final-01-hero.png" });
for (const id of ["geometry", "color", "apps", "rules", "assets"]) {
  await page.locator("#" + id).scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  await page.locator("#" + id).screenshot({ path: `${dir}/final-02-${id}.png` });
}

/* controls */
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(500);
await page.selectOption("#ctlBg", "light");
await page.waitForTimeout(400);
await page.locator("#heroStage").screenshot({ path: dir + "/final-03-light.png" });
await page.selectOption("#ctlBg", "deep");
await page.locator("label.switch:has(#ctlMono)").click();
await page.locator("label.switch:has(#ctlGrid)").click();
await page.locator("label.switch:has(#ctlLockup)").click();
await page.waitForTimeout(400);
await page.locator("#heroStage").screenshot({ path: dir + "/final-04-mono-grid-lockup.png" });
await page.locator("label.switch:has(#ctlMono)").click();
await page.locator("label.switch:has(#ctlGrid)").click();
await page.locator("label.switch:has(#ctlLockup)").click();
await page.locator("label.switch:has(#ctlMotion)").click();
const animOff = await page.evaluate(() => ({ bladeGroups: document.querySelectorAll("#heroBox .blade").length, staticPaths: document.querySelectorAll("#heroBox svg.mark path").length }));
console.log("motion off -> static render:", JSON.stringify(animOff));
await page.locator("label.switch:has(#ctlMotion)").click();
await page.locator("#ctlGlow").fill("100");
await page.locator("#ctlSize").fill("320");
await page.waitForTimeout(400);
await page.locator("#heroStage").screenshot({ path: dir + "/final-05-glow-size.png" });
await page.click("#ctlReset");
await page.waitForTimeout(300);

/* copy + export feedback */
await page.locator("[data-spec='1']").click();
await page.waitForTimeout(300);
console.log("spec copy toast:", await page.locator("#toastMsg").textContent());
await page.click("#cpSvg");
await page.waitForTimeout(300);
console.log("svg copy toast:", await page.locator("#toastMsg").textContent());
await page.click("#dlPng");
await page.waitForTimeout(1200);
console.log("png toast:", await page.locator("#toastMsg").textContent());

/* mobile */
await page.setViewportSize({ width: 390, height: 844 });
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(900);
await page.screenshot({ path: dir + "/final-06-mobile-hero.png" });
await page.locator("#assets").scrollIntoViewIfNeeded();
await page.waitForTimeout(800);
await page.screenshot({ path: dir + "/final-07-mobile-assets.png" });
console.log("mobile horizontal overflow px:", await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth));
console.log("console/page errors:", errors.length ? errors : "none");
await browser.close();