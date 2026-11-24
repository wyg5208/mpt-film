/* 实测浏览器回退字体下的文本宽度，用于校准字标 viewBox。
   Run: node docs/chango-wordmark/measure.mjs */
import { chromium } from "file:///D:/python_projects/moneyprintturbo/opensources/changovideo/node_modules/.pnpm/playwright-core@1.61.1/node_modules/playwright-core/index.mjs";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setContent(`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="220">
<text id="v" x="0" y="70" font-family="Inter,'Segoe UI','Helvetica Neue',Arial,sans-serif" font-size="56" font-weight="700" letter-spacing="-1">hangoVideo</text>
<text id="f1" x="0" y="150" font-family="Inter,'Segoe UI','Microsoft YaHei',sans-serif" font-size="56" font-weight="600">hango</text>
<text id="f2" x="300" y="150" font-family="Inter,'Segoe UI','Microsoft YaHei',sans-serif" font-size="56" font-weight="800">Film</text>
</svg>`);
const r = await page.evaluate(() => {
  const g = id => { const e = document.getElementById(id); const b = e.getBBox(); return { len: +e.getComputedTextLength().toFixed(2), x: +b.x.toFixed(2), w: +b.width.toFixed(2) }; };
  return { video: g("v"), hango: g("f1"), film: g("f2") };
});
console.log(JSON.stringify(r, null, 2));
await browser.close();