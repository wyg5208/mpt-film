/* Headless visual verification for the ChangoFilm logo proposal page.
   Run: node docs/changofilm-logo/verify.mjs   (screenshots -> docs/changofilm-logo/shots/) */
import { chromium } from "file:///D:/python_projects/moneyprintturbo/opensources/changovideo/node_modules/.pnpm/playwright-core@1.61.1/node_modules/playwright-core/index.mjs";
import { mkdirSync } from "node:fs";

const dir = "D:/python_projects/moneyprintturbo/docs/changofilm-logo/shots";
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const errors = [];
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", e => errors.push(e.message));

await page.goto("file:///D:/python_projects/moneyprintturbo/docs/changofilm-logo/index.html");
await page.waitForTimeout(1000);
await page.screenshot({ path: dir + "/01-hero.png" });

for (const id of ["c1", "c2", "c3", "c4", "c5"]) {
  await page.locator("#" + id).scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  await page.locator("#" + id).screenshot({ path: `${dir}/02-${id}.png` });
}
await page.locator("#compare").scrollIntoViewIfNeeded();
await page.waitForTimeout(800);
await page.locator("#compare").screenshot({ path: dir + "/03-compare.png" });

await page.selectOption("#ctlBg", "light");
await page.waitForTimeout(400);
await page.locator("#c1").scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
await page.locator("#c1 .stage").screenshot({ path: dir + "/04-c1-light.png" });

await page.selectOption("#ctlBg", "dark");
await page.locator("label.switch:has(#ctlMono)").click();
await page.locator("label.switch:has(#ctlGrid)").click();
await page.locator("label.switch:has(#ctlLockup)").click();
await page.waitForTimeout(400);
await page.locator("#c4").scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
await page.locator("#c4 .stage").screenshot({ path: dir + "/05-c4-mono-grid-lockup.png" });
await page.click("#ctlReset");
await page.waitForTimeout(300);

await page.setViewportSize({ width: 390, height: 844 });
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(800);
await page.screenshot({ path: dir + "/06-mobile-hero.png" });
await page.locator("#c1").scrollIntoViewIfNeeded();
await page.waitForTimeout(800);
await page.screenshot({ path: dir + "/07-mobile-c1.png" });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
console.log("mobile horizontal overflow px:", overflow);
console.log("console/page errors:", errors.length ? errors : "none");
await browser.close();