// One-off: verify the live-log dock contract on the real Mode A app (:8080).
// 1) default collapsed launcher (no .log-col column)
// 2) click -> modal at ~75vw with the real task's buffered log lines
// 3) ESC closes back to the launcher
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.VERIFY_BASE_URL || "http://localhost:8080";
const OUT = "../.verify";
mkdirSync(OUT, { recursive: true });
const TASK_ID =
  process.env.VERIFY_TASK_ID || "83da905f-bdaa-4c85-b34f-e2fc4fa3c656";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

await page.goto(`${BASE}/quick`);
await page.waitForSelector('[data-testid="shell-nav"]');
await page.waitForSelector('[data-testid="log-launcher"]');
console.log("launcher visible:", true);
console.log("log-col removed:", (await page.locator(".log-col").count()) === 0);
await page.screenshot({ path: `${OUT}/08-log-dock-collapsed.png` });

// seed the persisted current task, reload: dock must stay collapsed
await page.evaluate((id) => sessionStorage.setItem("cf_current_task", id), TASK_ID);
await page.reload();
await page.waitForSelector('[data-testid="log-launcher"]');
await page.waitForTimeout(800);
console.log(
  "collapsed after reload:",
  (await page.locator('[data-testid="log-modal"]').count()) === 0
);

await page.locator('[data-testid="log-launcher"]').click();
await page.waitForSelector('[data-testid="log-modal"]');
await page.waitForTimeout(500);
const box = await page.locator(".log-modal").boundingBox();
console.log("modal width:", Math.round(box.width), "(75vw of 1280 =", 960, ")");
console.log("log lines:", await page.locator('[data-testid="log-modal"] .logline').count());
await page.screenshot({ path: `${OUT}/07-log-dock-modal.png` });

await page.keyboard.press("Escape");
await page.waitForSelector('[data-testid="log-launcher"]');
console.log(
  "esc closes modal:",
  (await page.locator('[data-testid="log-modal"]').count()) === 0
);

await browser.close();
console.log("dock verify done");
