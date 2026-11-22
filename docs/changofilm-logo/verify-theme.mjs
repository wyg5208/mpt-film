/* Headless verification: ChangoFilm brand theme live in the Streamlit product (v1.9.0).
   Theme controls moved out of the left nav: driven here via the settings PAGE
   brand tab (cfpage_*); the settings DIALOG brand tab (cfset_*) is still probed
   for shared session state. The nav lockup must be absent everywhere.
   Run: node docs/changofilm-logo/verify-theme.mjs  ->  shots/v190-*.png
   Requires the app on http://127.0.0.1:8511 (restart Streamlit after edits). */
import { chromium } from "file:///D:/python_projects/moneyprintturbo/opensources/changovideo/node_modules/.pnpm/playwright-core@1.61.1/node_modules/playwright-core/index.mjs";
import { mkdirSync } from "node:fs";

const dir = "D:/python_projects/moneyprintturbo/docs/changofilm-logo/shots";
mkdirSync(dir, { recursive: true });
const URL = "http://127.0.0.1:8511";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
/* Mark the onboarding tour as seen before any script runs; the delayed
   auto-start otherwise pops the overlay mid-run. */
await page.addInitScript(() => {
  localStorage.setItem("stTour-changofilm-onboarding-v1", "1");
});
const errors = [];
const failures = [];
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", e => errors.push("PAGEERROR: " + e.message));
page.on("requestfailed", r => errors.push("REQ FAIL: " + r.url()));

const check = (name, ok, detail = "") => {
  console.log(`${ok ? "OK  " : "FAIL"} ${name}${detail ? " | " + detail : ""}`);
  if (!ok) failures.push(name);
};
const cssVar = n => page.evaluate(k => getComputedStyle(document.documentElement).getPropertyValue(k).trim(), n);
const waitVar = (n, v) => page.waitForFunction(
  ([k, val]) => getComputedStyle(document.documentElement).getPropertyValue(k).trim() === val,
  [n, v], { timeout: 30000 },
);
/* App container background: color sits in backgroundColor (last shorthand layer),
   gradients in backgroundImage — concat both and match the rgb() form. */
const appBgStr = () => page.evaluate(() => {
  const s = getComputedStyle(document.querySelector('[data-testid="stAppViewContainer"]'));
  return s.backgroundColor + " " + s.backgroundImage;
});
const mainColor = () => page.evaluate(() => getComputedStyle(document.querySelector('[data-testid="stMain"]')).color);
const navGone = () => page.evaluate(() => ({
  lockup: !!document.querySelector(".cf-nav-lockup"),
  navDeck: document.querySelectorAll('[class*="st-key-cfnav_"]').length,
}));
/* Streamlit selectbox: open by widget key class, pick option by index (locale-proof).
   A widget-driven full rerun can close a just-opened popup mid-click; retry the
   open->pick sequence after letting the rerun settle. */
async function pick(key, idx) {
  const box = page.locator(`.st-key-${key} [data-testid="stSelectbox"]`);
  await box.scrollIntoViewIfNeeded();
  for (let attempt = 1; ; attempt++) {
    await box.locator('[role="combobox"]').click();
    try {
      await page.waitForSelector('[role="listbox"] [role="option"]', { timeout: 6000 });
      await page.locator('[role="listbox"] [role="option"]').nth(idx).click();
      return;
    } catch (e) {
      if (attempt >= 3) throw e;
      console.log(`     pick(${key}) retry #${attempt} after popup race`);
      await page.keyboard.press("Escape").catch(() => {});
      await page.waitForTimeout(1200);
    }
  }
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
await page.waitForTimeout(2500);
await dismissTour(page);

/* 1. dark home: nav lockup/deck gone, dark defaults live */
const gone = await navGone();
check("nav lockup absent", !gone.lockup);
check("nav theme deck absent", gone.navDeck === 0);
check("no theme title on home", await page.evaluate(() => !document.querySelector(".cf-theme-title")));
await waitVar("--cf-accent", "#EC4899");
await waitVar("--cf-bg", "#0D0714");
check("dark --cf-bg", (await cssVar("--cf-bg")) === "#0D0714");
check("dark color-scheme", (await cssVar("color-scheme")) === "dark");
check("dark app bg", (await appBgStr()).includes("13, 7, 20"));
check("dark body text", (await mainColor()).includes("247, 242, 250"));
check("mark tri pale on dark", await page.evaluate(() =>
  getComputedStyle(document.querySelector(".cf-mark path:last-of-type")).fill.includes("245, 208, 254")));
check("favicon link present", await page.evaluate(() => !!document.querySelector('link[rel~="icon"]')));
console.log("     favicon href:", await page.evaluate(() => document.querySelector('link[rel~="icon"]')?.href || "none"));
await page.screenshot({ path: dir + "/v190-01-dark-home.png" });

/* 2. settings page -> brand theme TAB drives cfpage_* */
await page.locator(".st-key-nav_page_settings button").click();
await page.waitForSelector('.st-key-feature_page_settings div[role="tab"]', { timeout: 60000 });
await page.locator('.st-key-feature_page_settings div[role="tab"]').nth(4).click();
await page.waitForSelector(".st-key-cfpage_mode", { timeout: 30000 });
const panel = await page.evaluate(() => ({
  selects: document.querySelectorAll('[class*="st-key-feature_page_settings"] [data-testid="stSelectbox"]').length,
  sliders: document.querySelectorAll('[class*="st-key-feature_page_settings"] [data-testid="stSlider"]').length,
  toggles: document.querySelectorAll('[class*="st-key-feature_page_settings"] [data-testid="stToggle"], [class*="st-key-feature_page_settings"] [data-testid="stCheckbox"]').length,
  reset: !!document.querySelector(".st-key-cfpage_reset button"),
  lockup: !!document.querySelector(".cf-nav-lockup"),
  modeOptions: document.querySelectorAll('.st-key-cfpage_mode [role="combobox"]').length,
}));
check("cfpage panel inventory 4/2/2+reset", panel.selects === 4 && panel.sliders === 2 && panel.toggles === 2 && panel.reset,
  JSON.stringify(panel));
check("lockup still absent on settings page", !panel.lockup);
check("theme title inside settings page", await page.evaluate(() => !!document.querySelector(".cf-theme-title")));
await page.screenshot({ path: dir + "/v190-02-dark-settings-brand.png" });

/* 3. accent -> violet, field -> aurora (dark) */
await pick("cfpage_accent", 1);
await waitVar("--cf-accent", "#8B5CF6");
console.log("OK   accent violet, st-primary:", await cssVar("--st-primary-color"));
await pick("cfpage_field", 2);
await page.waitForFunction(() => getComputedStyle(document.documentElement).getPropertyValue("--cf-field-bg").includes("radial-gradient(circle at 18%"), null, { timeout: 30000 });
console.log("OK   field aurora");
await sliderMax("cfpage_glow");
await waitVar("--cf-glow", "100");
await sliderMax("cfpage_radius");
await waitVar("--cf-radius", "20px");
console.log("OK   glow 100 / radius 20px");
await page.screenshot({ path: dir + "/v190-03-dark-violet-aurora.png" });

/* 4. motion off + density compact + logo off (top-bar mark only now) */
await toggle("cfpage_motion");
await waitVar("--cf-play", "paused");
console.log("OK   motion paused");
await pick("cfpage_density", 1);
await waitVar("--cf-gap", "0.55rem");
console.log("OK   density compact");
await toggle("cfpage_logo");
await page.waitForSelector(".changofilm-brand__mark", { state: "detached", timeout: 30000 });
check("logo off removes top-bar mark", await page.evaluate(() => !document.querySelector(".changofilm-brand__mark")));
check("lockup still absent after logo off", await page.evaluate(() => !document.querySelector(".cf-nav-lockup")));
const rawHtmlLeak = await page.evaluate(() => (document.querySelector('[class*="st-key-top_bar"]')?.textContent || "").includes("<span"));
check("no raw-html leak", !rawHtmlLeak);
await page.screenshot({ path: dir + "/v190-04-dark-compact-nologo.png" });

/* 5. light mode: palette swap + Streamlit overrides + softened shadows */
await pick("cfpage_mode", 1);
await waitVar("--cf-bg", "#F4F1F8");
check("light --cf-bg", (await cssVar("--cf-bg")) === "#F4F1F8");
check("light color-scheme", (await cssVar("color-scheme")) === "light");
check("light --cf-ink", (await cssVar("--cf-ink")) === "#1D1330");
check("light --st-text-color override", (await cssVar("--st-text-color")) === "#1D1330");
check("light app bg flip", (await appBgStr()).includes("244, 241, 248"));
check("light body text readable", (await mainColor()).includes("29, 19, 48"));
check("light shadow softened", (await cssVar("--cf-shadow-strong")).includes("29, 19, 48"));
/* top-of-page evidence: settings tab row + brand h1 under light mode */
await page.evaluate(() => {
  const m = document.querySelector('[data-testid="stMain"]');
  if (m) m.scrollTop = 0;
  window.scrollTo(0, 0);
});
await page.waitForTimeout(600);
await page.screenshot({ path: dir + "/v190-05a-light-top.png" });
/* open dropdown menu evidence under light mode */
const menuBox = page.locator('.st-key-cfpage_density [data-testid="stSelectbox"]');
await menuBox.scrollIntoViewIfNeeded();
await menuBox.locator('[role="combobox"]').click();
await page.waitForSelector('[role="listbox"] [role="option"]', { timeout: 10000 });
await page.waitForTimeout(400);
await page.screenshot({ path: dir + "/v190-05b-light-menu-open.png" });
await page.keyboard.press("Escape");
await page.waitForTimeout(400);
/* logo back on so the top-bar mark proves the play triangle follows mode */
await toggle("cfpage_logo");
await page.waitForSelector(".changofilm-brand__mark", { timeout: 30000 });
await waitVar("--cf-mark-tri", "#6D28D9");
check("light mark tri uses accent deep", await page.evaluate(() =>
  getComputedStyle(document.querySelector(".cf-mark path:last-of-type")).fill.includes("109, 40, 217")));
await page.screenshot({ path: dir + "/v190-05-light-violet-aurora.png" });

/* 6. light deep field + reset restores dark defaults */
await pick("cfpage_field", 0);
await page.waitForFunction(() => {
  const v = getComputedStyle(document.documentElement).getPropertyValue("--cf-field-bg");
  return v.includes("radial-gradient(circle at 50%") && v.includes("#F4F1F8");
}, null, { timeout: 30000 });
console.log("OK   light deep field");
await page.screenshot({ path: dir + "/v190-06-light-deep.png" });
await page.locator(".st-key-cfpage_reset button").click();
await waitVar("--cf-accent", "#EC4899");
await waitVar("--cf-bg", "#0D0714");
await waitVar("--cf-play", "running");
await waitVar("--cf-gap", "1rem");
await waitVar("--cf-mark-tri", "#F5D0FE");
check("reset restores dark + widgets synced",
  (await cssVar("--cf-bg")) === "#0D0714" &&
  (await page.evaluate(() => !document.querySelector(".changofilm-brand__mark")) === false));
check("reset re-shows top-bar mark", await page.evaluate(() => !!document.querySelector(".changofilm-brand__mark")));
/* waitVar passes mid-rerun; let the widget states settle before the dialog step
   (opening the dialog too early races the reset rerun and shows stale cfset_*). */
await page.waitForTimeout(1500);

/* 7. settings dialog brand tab shares the same session theme (cfset_*) */
await page.locator(".st-key-open_settings_dialog_button button").click();
await page.waitForSelector('[data-testid="stDialog"]', { timeout: 30000 });
await page.locator('[data-testid="stDialog"] div[role="tab"]').nth(7).click();
await page.waitForSelector(".st-key-cfset_mode", { timeout: 30000 });
await page.waitForTimeout(600);
check("dialog cfset panel present", await page.evaluate(() =>
  !!document.querySelector(".st-key-cfset_mode") && !!document.querySelector(".st-key-cfset_accent")));
await pick("cfset_accent", 2);
await waitVar("--cf-accent", "#22D3EE");
console.log("OK   dialog brand tab cyan shared");
await page.screenshot({ path: dir + "/v190-07-dialog-brand.png" });
await page.locator('[data-testid="stDialog"] button[aria-label="Close"]').click();
await page.waitForSelector('[data-testid="stDialog"]', { state: "detached", timeout: 30000 });
/* The page yielded to the dialog, so the tabs widget state was dropped and the
   settings page re-renders on the first tab — re-select the brand tab. */
await page.waitForSelector('.st-key-feature_page_settings div[role="tab"]', { timeout: 30000 });
await page.locator('.st-key-feature_page_settings div[role="tab"]').nth(4).click();
await page.waitForSelector(".st-key-cfpage_reset", { timeout: 30000 });
await page.locator(".st-key-cfpage_reset button").click();
await waitVar("--cf-accent", "#EC4899");
await page.waitForTimeout(1200);

/* 8. creation workflow intact (back on quick page) */
await page.locator(".st-key-nav_page_quick button").click();
await page.waitForSelector('[class*="st-key-main_settings_grid"]', { timeout: 60000 });
await page.waitForTimeout(1500);
const workflow = await page.evaluate(() => ({
  tabs: document.querySelectorAll('[class*="st-key-main_settings_grid"] div[role="tab"]').length,
  textareas: document.querySelectorAll('[data-testid="stTextArea"]').length,
  primaryButtons: document.querySelectorAll('button[data-testid="stBaseButton-primary"]').length,
  lockup: !!document.querySelector(".cf-nav-lockup"),
}));
check("creation workflow intact", workflow.tabs > 0 && workflow.primaryButtons > 0 && !workflow.lockup,
  JSON.stringify(workflow));

/* 9. mobile viewport: no nav lockup, brand intact, no overflow */
const mob = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mob.addInitScript(() => {
  localStorage.setItem("stTour-changofilm-onboarding-v1", "1");
});
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
  lockup: !!document.querySelector(".cf-nav-lockup"),
  navDeck: document.querySelectorAll('[class*="st-key-cfnav_"]').length,
}));
check("mobile layout clean", mobile.overflow <= 0 && mobile.tabBar && mobile.mark && !mobile.lockup && mobile.navDeck === 0,
  JSON.stringify(mobile));
await mob.screenshot({ path: dir + "/v190-08-mobile.png" });

console.log("console/page errors:", errors.length ? errors : "none");
if (mobErrors.length) console.log("mobile pageerrors:", mobErrors);
console.log(failures.length ? `FAILED CHECKS (${failures.length}): ${failures.join(" | ")}` : "ALL CHECKS PASSED");
await browser.close();
process.exit(failures.length ? 1 : 0);
