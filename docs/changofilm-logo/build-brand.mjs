/* ChangoFilm 定稿商标「霓虹快门 Shutter C」全套品牌资产生成器
   Run: node docs/changofilm-logo/build-brand.mjs  ->  docs/changofilm-logo/brand/ */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync, statSync } from "node:fs";
const require = createRequire(import.meta.url);
const { Resvg } = require("D:/python_projects/moneyprintturbo/opensources/tools/chango-icon/node_modules/@resvg/resvg-js/index.js");

const OUT = "D:/python_projects/moneyprintturbo/docs/changofilm-logo/brand";
mkdirSync(OUT, { recursive: true });

/* ---- geometry: identical to the selected candidate 03 ---- */
const BLADE = "M50 10 A40 40 0 0 1 84.64 30 L62 42 A16 16 0 0 0 50 34 Z";
const ROTS = [0, 120, 180, 240, 300];
const TRI = "M62 42 L62 58 L76 50 Z";
const MAG = "#EC4899", VIO = "#8B5CF6", PALE = "#F5D0FE";

function markInner({ mono } = {}){
  const fill = mono || "url(#cf-g)";
  const defs = mono ? "" : `<linearGradient id="cf-g" gradientUnits="userSpaceOnUse" x1="50" y1="10" x2="84" y2="42"><stop offset="0" stop-color="${MAG}"/><stop offset="1" stop-color="${VIO}"/></linearGradient>`;
  const blades = ROTS.map(r => `<path d="${BLADE}" transform="rotate(${r} 50 50)" fill="${fill}"/>`).join("");
  return `<defs>${defs}</defs>${blades}<path d="${TRI}" fill="${mono || PALE}"/>`;
}
const svgWrap = (inner, vb = "0 0 100 100", w = 1024, h = 1024) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" width="${w}" height="${h}">${inner}</svg>`;

function lockup(light){
  const ink = light ? "#201030" : "#F7F2FA";
  const filmFill = light ? "#C026D3" : "url(#cf-lk)";
  const defs = light ? "" : `<linearGradient id="cf-lk" gradientUnits="userSpaceOnUse" x1="228" y1="50" x2="334" y2="50"><stop offset="0" stop-color="${MAG}"/><stop offset="1" stop-color="${VIO}"/></linearGradient>`;
  return svgWrap(`<defs>${defs}</defs><g transform="translate(4 4) scale(0.92)">${markInner()}</g>
    <text x="112" y="64" font-family="Inter,'Segoe UI','Microsoft YaHei',sans-serif" font-size="37" font-weight="600" fill="${ink}">Chango<tspan font-weight="800" fill="${filmFill}">Film</tspan></text>`, "0 0 340 100", 1360, 400);
}
const maskable = svgWrap(`<rect width="100" height="100" fill="#1B0B2E"/><g transform="translate(50 50) scale(0.72) translate(-50 -50)">${markInner()}</g>`);

/* ---- raster + containers ---- */
const png = (svg, width) => Buffer.from(new Resvg(svg, {
  background: "rgba(0,0,0,0)", fitTo: { mode: "width", value: width }, font: { loadSystemFonts: true }
}).render().asPng());

function ico(entries){
  const head = Buffer.alloc(6);
  head.writeUInt16LE(0, 0); head.writeUInt16LE(1, 2); head.writeUInt16LE(entries.length, 4);
  let off = 6 + 16 * entries.length; const dirs = [], blobs = [];
  for (const [size, buf] of entries){
    const e = Buffer.alloc(16);
    e.writeUInt8(size >= 256 ? 0 : size, 0); e.writeUInt8(size >= 256 ? 0 : size, 1);
    e.writeUInt16LE(1, 4); e.writeUInt16LE(32, 6);
    e.writeUInt32LE(buf.length, 8); e.writeUInt32LE(off, 12);
    off += buf.length; dirs.push(e); blobs.push(buf);
  }
  return Buffer.concat([head, ...dirs, ...blobs]);
}
function icns(entries){
  const chunks = entries.map(([type, buf]) => {
    const h = Buffer.alloc(8); h.write(type, 0, "ascii"); h.writeUInt32BE(buf.length + 8, 4);
    return Buffer.concat([h, buf]);
  });
  const head = Buffer.alloc(8); head.write("icns", 0, "ascii");
  head.writeUInt32BE(8 + chunks.reduce((s, c) => s + c.length, 0), 4);
  return Buffer.concat([head, ...chunks]);
}

/* ---- emit ---- */
const files = [];
const emit = (name, data, label, fmt, dims, use) => {
  writeFileSync(`${OUT}/${name}`, data);
  files.push({ file: name, label, fmt, dims, bytes: statSync(`${OUT}/${name}`).size, use });
};
const master = svgWrap(markInner());
emit("changofilm-mark.svg", master, "主商标矢量源", "SVG", "viewBox 100", "无损缩放源文件 / 一切衍生的母版");
const markPngs = {};
for (const s of [16, 32, 48, 192, 512, 1024]){
  markPngs[s] = png(master, s);
  emit(`changofilm-mark-${s}.png`, markPngs[s], `主商标 ${s}px`, "PNG", `${s}×${s}`, s <= 48 ? "favicon / 小尺寸界面" : s <= 512 ? "PWA / 社交头像 / 文档" : "母版位图 / 片头水印");
}
const p256 = png(master, 256), p128 = png(master, 128);
const icoBuf = ico([[16, markPngs[16]], [32, markPngs[32]], [48, markPngs[48]], [256, p256]]);
emit("changofilm-icon.ico", icoBuf, "Windows 图标", "ICO", "16/32/48/256", "桌面端 exe / 任务栏 / 资源管理器");
const icnsBuf = icns([["ic07", p128], ["ic08", p256], ["ic09", markPngs[512]], ["ic10", markPngs[1024]]]);
emit("changofilm-icon.icns", icnsBuf, "macOS 图标", "ICNS", "128/256/512/1024", "桌面端 .app / Dock");
emit("changofilm-maskable.svg", maskable, "Maskable 矢量", "SVG", "viewBox 100", "PWA maskable 源（含安全区底色）");
emit("changofilm-maskable-512.png", png(maskable, 512), "Maskable 512px", "PNG", "512×512", "PWA manifest maskable 图标");
const lkD = lockup(false), lkL = lockup(true);
emit("changofilm-lockup-dark.svg", lkD, "横版字标 · 深底", "SVG", "340×100", "深色界面 / 片头 / 官网导航");
emit("changofilm-lockup-light.svg", lkL, "横版字标 · 浅底", "SVG", "340×100", "浅色纸面 / 文档 / 合同抬头");
emit("changofilm-lockup-dark.png", png(lkD, 1360), "横版字标 · 深底位图", "PNG", "1360×400", "深底位图场景");
emit("changofilm-lockup-light.png", png(lkL, 1360), "横版字标 · 浅底位图", "PNG", "1360×400", "浅底位图场景");
emit("changofilm-mono-dark.svg", svgWrap(markInner({ mono: "#F7F2FA" })), "单色 · 反白", "SVG", "viewBox 100", "单色印刷 / 雕刻 / 深底水印");
emit("changofilm-mono-light.svg", svgWrap(markInner({ mono: "#201030" })), "单色 · 墨版", "SVG", "viewBox 100", "单色印刷 / 传真 / 浅底水印");

/* ---- integrity checks ---- */
const icoBack = icoBuf.readUInt16LE(4);
const icnsLen = icnsBuf.readUInt32BE(4);
console.log(`ico entries: ${icoBack} (expect 4) | icns declared length: ${icnsLen} == file size: ${icnsBuf.length} -> ${icnsLen === icnsBuf.length}`);

writeFileSync(`${OUT}/manifest.js`, `window.BRAND_MANIFEST = ${JSON.stringify(files, null, 2)};\n`);
console.log(`emitted ${files.length} assets + manifest.js -> ${OUT}`);