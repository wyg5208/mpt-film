/* Chango 双品牌「文字合一」字标 v2 资产生成器
   Run: node docs/chango-wordmark/build-wordmark.mjs  ->  docs/chango-wordmark/brand/ */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync, statSync } from "node:fs";
const require = createRequire(import.meta.url);
const { Resvg } = require("D:/python_projects/moneyprintturbo/opensources/tools/chango-icon/node_modules/@resvg/resvg-js/index.js");
const WM = require("./wordmark.js");

const OUT = "D:/python_projects/moneyprintturbo/docs/chango-wordmark/brand";
mkdirSync(OUT, { recursive: true });

const png = (svg, width) => Buffer.from(new Resvg(svg, {
  background: "rgba(0,0,0,0)", fitTo: { mode: "width", value: width }, font: { loadSystemFonts: true }
}).render().asPng());

const files = [];
const emit = (name, data, label, fmt, dims, use) => {
  writeFileSync(`${OUT}/${name}`, data);
  files.push({ file: name, label, fmt, dims, bytes: statSync(`${OUT}/${name}`).size, use });
};

const VARIANTS = [
  { suffix: "light",      opts: { dark: false },                    label: "浅底", use: "浅色纸面 / 文档 / 浅色界面导航" },
  { suffix: "dark",       opts: { dark: true },                     label: "深底", use: "深色界面 / 片头 / 官网导航" },
  { suffix: "mono-light", opts: { dark: false, mono: "INK_LIGHT" }, label: "单色墨版", use: "单色印刷 / 传真 / 浅底水印" },
  { suffix: "mono-dark",  opts: { dark: true,  mono: "INK_DARK" },  label: "单色反白", use: "单色印刷 / 雕刻 / 深底水印" },
];

for (const brand of ["video", "film"]) {
  const b = brand === "video" ? WM.VIDEO : WM.FILM;
  for (const v of VARIANTS) {
    const opts = { ...v.opts };
    if (opts.mono === "INK_LIGHT") opts.mono = b.inkLight;
    if (opts.mono === "INK_DARK") opts.mono = b.inkDark;
    const svg = WM.wordmarkSvg(brand, opts);
    const w = b.vbW * 4;
    const base = `chango${brand}-wordmark-${v.suffix}`;
    emit(`${base}.svg`, svg, `${b.name} 字标 · ${v.label}`, "SVG", `${b.vbW}×100`, v.use);
    emit(`${base}.png`, png(svg, w), `${b.name} 字标 · ${v.label}位图`, "PNG", `${w}×400`, v.use + "（位图场景）");
  }
}

writeFileSync(`${OUT}/manifest.js`, `window.WORDMARK_MANIFEST = ${JSON.stringify(files, null, 2)};\n`);
console.log(`emitted ${files.length} assets + manifest.js -> ${OUT}`);