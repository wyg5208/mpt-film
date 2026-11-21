/* Headless verification: ChangoFilm brand theme live in the Streamlit product.
   Run: node docs/changofilm-logo/verify-theme.mjs  ->  shots/theme-*.png
   Requires the app on http://127.0.0.1:8511 (see launch command in docs). */
import { chromium } from "file:///D:/python_projects/moneyprintturbo/opensources/changovideo/node_modules/.pnpm/playwright-core@1.61.1/node_modules/playwright-core/index.mjs";
import { mkdirSync } from "node:fs";

const dir = "D:/python_projects/moneyprintturbo/docs/changofilm-logo/shots";
mkdirSync(dir, { recursive: true });
const URL = "http://127.0.0.1:8511";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const errors = [];
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", e => errors.push("PAGEERROR: " + e.message));
page.on("requestfailed", r => errors.push("REQ FAIL: " + r.url()));

const cssVar = n => page.evaluate(k => getComputedStyle(document.documentElement).getPropertyValue(k).trim(), n);
const waitVar = (n, v) => page.waitForFunction(
  ([k, val]) => getComputedStyle(document.documentElement).getPropertyValue(k).trim() === val,
  [n, v], { timeout: 30000 },
);
/* Streamlit selectbox: open by widget key class, pick option by index (locale-proof). */
async function pick(key, idx) {
  const box = page.locator(`.st-key-${key} [data-testid="stSelectbox"]`);
  await box.scrollIntoViewIfNeeded();
  await box.locator('[role="combobox"]').click();
  await page.waitForSelector('[role="listbox"] [role="option"]', { timeout: 10000 });
  await page.locator('[role="listbox"] [role="option"]').nth(idx).click();
}
async function toggle(key) {
  await page.locator(`.st-key-${key} label`).first().click();
}
async function sliderMax(key) {
  await page.locator(`.st-key-${key} input[type="range"]`).focus();
  await page.keyboard.press("End");
}
/* First-visit onboarding tour (driver.js) blocks pointer events; dismiss it. */
async function dismissTour(p) {
  for (const sel of [".driver-popover-close-btn", ".driver-close-btn"]) {
    const b = p.locator(sel);
    if (await b.count()) { await b.first().click({ force: true }).catch(() => {}); await p.waitForTimeout(500); }
  }
  if (await p.locator(".driver-overlay").count()) {
    await p.keyboard.press("Escape"); await p.waitForTimeout(500);
  }
  if (await p.locator(".driver-overlay").count()) {
    await p.locator(".driver-overlay").click({ force: true, position: { x: 5, y: 5 } }).catch(() => {});
    await p.waitForTimeout(500);
  }
}

await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForSelector(".changofilm-brand", { timeout: 90000 });
await page.waitForSelector(".cf-theme-title", { timeout: 90000 });
await page.waitForTimeout(2500);
await dismissTour(page);

/* 1. theme variables + favicon + background field */
console.log("accent:", await cssVar("--cf-accent"), "| st-primary:", await cssVar("--st-primary-color"));
console.log("favicon:", await page.evaluate(() => document.querySelector('link[rel~="icon"]')?.href || "none"));
const appBg = await page.evaluate(() => getComputedStyle(document.querySelector('[data-testid="stAppViewContainer"]')).backgroundImage);
console.log("app background:", appBg.slice(0, 90));

/* 2. brand mark in h1 + nav lockup + glow animation */
const brand = await page.evaluate(() => ({
  h1Mark: !!document.querySelector(".changofilm-brand__mark svg"),
  navLockup: !!document.querySelector(".cf-nav-lockup svg"),
  nameGradient: getComputedStyle(document.querySelector(".changofilm-brand__name")).backgroundImage.includes("linear-gradient"),
  markAnim: getComputedStyle(document.querySelector(".cf-mark")).animationName,
  play: getComputedStyle(document.documentElement).getPropertyValue("--cf-play").trim(),
}));
console.log("brand:", JSON.stringify(brand));

/* 3. control deck inventory in nav (3 selects + 2 sliders + 2 toggles + reset) */
const deck = await page.evaluate(() => ({
  selects: document.querySelectorAll('[class*="st-key-nav_sidebar_"] [data-testid="stSelectbox"]').length,
  sliders: document.querySelectorAll('[class*="st-key-nav_sidebar_"] [data-testid="stSlider"]').length,
  toggles: document.querySelectorAll('[class*="st-key-nav_sidebar_"] [data-testid="stToggle"], [class*="st-key-nav_sidebar_"] [data-testid="stCheckbox"]').length,
  reset: !!document.querySelector(".st-key-cfnav_reset button"),
}));
console.log("nav deck:", JSON.stringify(deck));

/* 4. primary button gradient + glow */
const initialAccent = await page.evaluate(() => document.querySelector('.st-key-cfnav_accent [role="combobox"]')?.value);
const btn = await page.evaluate(() => {
  const b = document.querySelector('button[data-testid="stBaseButton-primary"]');
  const s = getComputedStyle(b);
  return { gradient: s.backgroundImage.includes("linear-gradient"), radius: s.borderRadius, shadow: s.boxShadow !== "none" };
});
console.log("primary button:", JSON.stringify(btn));
await page.screenshot({ path: dir + "/theme-01-desktop-default.png" });

/* 5. accent switch -> violet */
await pick("cfnav_accent", 1);
await waitVar("--cf-accent", "#8B5CF6");
console.log("accent violet OK, st-primary:", await cssVar("--st-primary-color"));

/* 6. field -> aurora */
await pick("cfnav_field", 2);
await page.waitForFunction(() => getComputedStyle(document.documentElement).getPropertyValue("--cf-field-bg").includes("radial-gradient(circle at 18%"), null, { timeout: 30000 });
console.log("field aurora OK");
await page.waitForTimeout(800);
await page.screenshot({ path: dir + "/theme-02-violet-aurora.png" });

/* 7. glow + radius sliders live */
await sliderMax("cfnav_glow");
await waitVar("--cf-glow", "100");
await sliderMax("cfnav_radius");
await waitVar("--cf-radius", "20px");
const r20 = await page.evaluate(() => getComputedStyle(document.querySelector('button[data-testid="stBaseButton-primary"]')).borderRadius);
console.log("glow 100 / radius 20px OK, button radius:", r20);

/* 8. motion off -> paused */
await toggle("cfnav_motion");
await waitVar("--cf-play", "paused");
console.log("motion paused OK");

/* 9. density compact */
await pick("cfnav_density", 1);
await waitVar("--cf-gap", "0.55rem");
console.log("density compact OK");

/* 10. logo off -> marks removed */
await toggle("cfnav_logo");
await page.waitForSelector(".changofilm-brand__mark", { state: "detached", timeout: 30000 });
await page.waitForSelector(".cf-nav-lockup", { state: "detached", timeout: 30000 });
const rawHtmlLeak = await page.evaluate(() => (document.querySelector('[class*="st-key-top_bar"]')?.textContent || "").includes("<span"));
console.log("logo hidden OK, raw-html leak:", rawHtmlLeak);
await page.screenshot({ path: dir + "/theme-03-compact-nologo.png" });

/* 11. reset restores defaults */
await page.locator(".st-key-cfnav_reset button").click();
await waitVar("--cf-accent", "#EC4899");
await waitVar("--cf-play", "running");
await waitVar("--cf-gap", "1rem");
await page.waitForSelector(".changofilm-brand__mark svg", { timeout: 30000 });
const resetAccent = await page.evaluate(() => document.querySelector('.st-key-cfnav_accent [role="combobox"]')?.value);
console.log("reset OK, widget synced back to default:", resetAccent === initialAccent);

/* 12. settings dialog brand tab shares state */
await page.locator(".st-key-open_settings_dialog_button button").click();
await page.waitForSelector('[data-testid="stDialog"]', { timeout: 30000 });
await page.locator('[data-testid="stDialog"] div[role="tab"]').nth(7).click();
await page.waitForSelector(".st-key-cfset_accent", { timeout: 30000 });
await page.waitForTimeout(600);
console.log("raw-html leak after reset+dialog:", await page.evaluate(() => (document.querySelector('[class*="st-key-top_bar"]')?.textContent || "").includes("<span")));
await page.screenshot({ path: dir + "/theme-04-dialog-brand.png" });
await pick("cfset_accent", 2);
await waitVar("--cf-accent", "#22D3EE");
console.log("dialog brand tab cyan OK");
await page.locator('[data-testid="stDialog"] button[aria-label="Close"]').click();
await page.waitForSelector('[data-testid="stDialog"]', { state: "detached", timeout: 30000 });
await page.locator(".st-key-cfnav_reset button").click();
await waitVar("--cf-accent", "#EC4899");

/* 13. creation workflow intact */
const workflow = await page.evaluate(() => ({
  tabs: document.querySelectorAll('[class*="st-key-main_settings_grid"] div[role="tab"]').length,
  textareas: document.querySelectorAll('[data-testid="stTextArea"]').length,
  primaryButtons: document.querySelectorAll('button[data-testid="stBaseButton-primary"]').length,
}));
console.log("creation workflow:", JSON.stringify(workflow));

/* 14. mobile viewport */
const mob = await browser.newPage({ viewport: { width: 390, height: 844 } });
const mobErrors = [];
mob.on("pageerror", e => mobErrors.push(e.message));
await mob.goto(URL, { waitUntil: "domcontentloaded" });
await mob.waitForSelector(".changofilm-brand", { timeout: 90000 });
await mob.waitForTimeout(2500);
await dismissTour(mob);
const mobile = await mob.evaluate(() => ({
  overflow: document.documentElement.scrollWidth - window.innerWidth,
  tabBar: !!document.querySelector('[class*="st-key-mobile_tab_bar"]'),
  mark: !!document.querySelector(".changofilm-brand__mark svg"),
  markSize: document.querySelector(".changofilm-brand__mark svg")?.getBoundingClientRect().width,
}));
console.log("mobile:", JSON.stringify(mobile), "| pageerrors:", mobErrors.length);
await mob.screenshot({ path: dir + "/theme-05-mobile.png" });

console.log("console/page errors:", errors.length ? errors : "none");
await browser.close();