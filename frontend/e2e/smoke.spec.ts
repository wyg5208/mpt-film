// SPA smoke e2e (migration Phase 3.4): exercises shell navigation and every
// Phase 2 page against the real FastAPI backend through the vite proxy
// (Mode A, auth-free because config.api_key is empty).
import { test, expect } from "@playwright/test";

test("shell nav exposes all five product areas", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByTestId("shell-nav");
  await expect(nav).toBeVisible();
  for (const label of ["Generate", "Tasks", "Series", "Publish", "Settings"]) {
    await expect(nav.getByText(label, { exact: true })).toBeVisible();
  }
});

test("generate page renders the golden param controls", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Generate video" })).toBeVisible();
  await expect(page.locator("input").first()).toBeVisible();
});

test("tasks page loads from the API", async ({ page }) => {
  await page.goto("/jobs");
  await expect(page.locator(".content")).toBeVisible();
  // backend must answer the task list request through the proxy
  const resp = await page.request.get("/api/v1/tasks?page=1&page_size=10");
  expect(resp.ok()).toBeTruthy();
});

test("settings page shows section editor and cards", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByTestId("settings-section-app")).toBeVisible();
  await expect(page.getByTestId("settings-keys")).toBeVisible();
  await expect(page.getByTestId("settings-presets")).toBeVisible();
  await expect(page.getByTestId("settings-cache")).toBeVisible();
  await expect(page.getByTestId("oauth-chatgpt")).toBeVisible();
});

test("settings credential fields are masked, never raw", async ({ page }) => {
  await page.goto("/settings");
  // every *_api_key / *_secret_key style value must come back as a masked view
  const problems: string[] = [];
  for (const section of ["app", "azure", "siliconflow"]) {
    const resp = await page.request.get(`/api/v1/settings/${section}`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    for (const [key, value] of Object.entries<any>(body.data ?? {})) {
      if (/(api_key|api_keys|api_token|access_key|secret_key|speech_key)$/.test(key)) {
        if (typeof value !== "object" || !("masked" in value) || !("configured" in value)) {
          problems.push(`${section}.${key} is not masked`);
        }
      }
    }
  }
  expect(problems).toEqual([]);
});

test("series page lists and creates", async ({ page }) => {
  await page.goto("/series");
  await expect(page.getByTestId("series-list")).toBeVisible();
  const title = `e2e-${Date.now()}`;
  await page.getByTestId("series-list").getByPlaceholder("Series title").fill(title);
  await page.getByRole("button", { name: "New series" }).click();
  await expect(page.getByTestId("series-detail")).toBeVisible();
  await expect(page).toHaveURL(/\/series\/.+/);
  // clean up
  const sid = page.url().split("/").pop();
  await page.request.delete(`/api/v1/series/${sid}`);
});

test("episode status machine blocks illegal backward moves", async ({ page }) => {
  const resp = await page.request.post("/api/v1/series", {
    data: { title: `e2e-sm-${Date.now()}`, genre_template: "custom" },
  });
  const sid = (await resp.json()).data.id;
  const epResp = await page.request.post(`/api/v1/series/${sid}/episodes`, {
    data: { title: "ep1", logline: "", hook: "" },
  });
  const eid = (await epResp.json()).data.id;
  // draft -> rendered is not a forward single step: must be rejected (409)
  const bad = await page.request.patch(
    `/api/v1/series/${sid}/episodes/${eid}/status`,
    { data: { status: "rendered" } }
  );
  expect(bad.status()).toBe(409);
  const ok = await page.request.patch(
    `/api/v1/series/${sid}/episodes/${eid}/status`,
    { data: { status: "confirmed" } }
  );
  expect(ok.status()).toBe(200);
  await page.request.delete(`/api/v1/series/${sid}`);
});

test("publish page shows queue, republish and history", async ({ page }) => {
  await page.goto("/publish");
  await expect(page.getByTestId("publish-queue")).toBeVisible();
  await expect(page.getByTestId("publish-republish")).toBeVisible();
  await expect(page.getByTestId("publish-history")).toBeVisible();
});

test("SPA fallback deep links resolve to the app, not 404", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByTestId("shell-nav")).toBeVisible();
  await page.goto("/series/nonexistent");
  // detail view must render the SPA shell (error state inside), not a server 404
  await expect(page.getByTestId("shell-nav")).toBeVisible();
});

test("language switch persists and survives reload", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("lang-select").selectOption("zh");
  expect(await page.evaluate(() => localStorage.getItem("cf_lang"))).toBe("zh");
  await page.reload();
  await expect(page.getByTestId("shell-nav")).toBeVisible();
  // the lazily loaded zh pack must not break rendering; nav still shows links
  await expect(page.getByTestId("lang-select")).toHaveValue("zh");
});
