/* Chango 双品牌「文字合一」字标 v2 —— 共享几何与渲染（浏览器 / Node 双端可用）
   核心规则：LOGO 直接充当首字母 C，后接 hangoVideo / hangoFilm。
   - 统一字号 F=56、基线 B=70（viewBox 高 100）
   - mark 视觉高度 = 0.80F：圆形字母相对大写字高（0.727F）上下各做约 4% 光学超出
   - mark 垂直中心对齐大写字高中心，左缘固定在 x=8
   - mark 右缘与 h 竖笔间距 ≈ 5px，模拟 C→h 的正常字距
   Run（资产生成）: node docs/chango-wordmark/build-wordmark.mjs */
(function (root) {
  "use strict";
  const F = 56, B = 70;
  const CAP = 0.727 * F, XH = 0.546 * F;      /* Inter 实测字高比例 */
  const capTop = B - CAP, xTop = B - XH, mid = (capTop + B) / 2;
  const H = 0.80 * F;                          /* mark 视觉高度（含 overshoot） */

  const VIDEO = {
    key: "video", name: "ChangoVideo",
    /* A1 mark 圆环含描边纵向范围 9.5..90.5，共 81 单位 */
    s: H / 81, tx: 8 - 9.5 * (H / 81), ty: mid - 50 * (H / 81),
    textX: 53, vbW: 376,   /* 53 + 实测 309.1 + 右留白 14（measure.mjs） */
    grad: ["#0D9488", "#22D3EE"],
    inkLight: "#111111", inkDark: "#F7F9FB",
    font: "Inter,'Segoe UI','Helvetica Neue',Arial,sans-serif",
  };
  const FILM = {
    key: "film", name: "ChangoFilm",
    /* 快门 C 叶片外径 40，纵向范围 10..90，共 80 单位 */
    s: H / 80, tx: 8 - 10 * (H / 80), ty: mid - 50 * (H / 80),
    textX: 54, vbW: 346,   /* 54 + 161.7 + 118.0 + 右留白 12（measure.mjs） */
    grad: ["#EC4899", "#8B5CF6"], pale: "#F5D0FE",
    inkLight: "#201030", inkDark: "#F7F2FA",
    font: "Inter,'Segoe UI','Microsoft YaHei',sans-serif",
  };

  /* 与定稿母版完全一致的两枚 mark 内部几何 */
  function markInner(brand, mono) {
    if (brand === "video") {
      const fill = mono || "url(#cg)";
      const defs = mono ? "" :
        `<linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${VIDEO.grad[0]}"/><stop offset="1" stop-color="${VIDEO.grad[1]}"/></linearGradient>`;
      return `<defs>${defs}<mask id="co" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100"><rect width="100" height="100" fill="#fff"/><path d="M50 50 L100 10 L100 90 Z" fill="#000"/></mask></defs>` +
        `<g mask="url(#co)"><circle cx="50" cy="50" r="33" fill="none" stroke="${fill}" stroke-width="15"/></g>` +
        `<path d="M60 39 L60 61 L79 50 Z" fill="${fill}" stroke="${fill}" stroke-width="5" stroke-linejoin="round"/>`;
    }
    const fill = mono || "url(#cf-g)";
    const defs = mono ? "" :
      `<linearGradient id="cf-g" gradientUnits="userSpaceOnUse" x1="50" y1="10" x2="84" y2="42"><stop offset="0" stop-color="${FILM.grad[0]}"/><stop offset="1" stop-color="${FILM.grad[1]}"/></linearGradient>`;
    const blade = "M50 10 A40 40 0 0 1 84.64 30 L62 42 A16 16 0 0 0 50 34 Z";
    const blades = [0, 120, 180, 240, 300].map(r => `<path d="${blade}" transform="rotate(${r} 50 50)" fill="${fill}"/>`).join("");
    return `<defs>${defs}</defs>${blades}<path d="M62 42 L62 58 L76 50 Z" fill="${mono || FILM.pale}"/>`;
  }

  /* 结构网格：大写字高线 / x 字高线 / 基线 */
  function gridOverlay(b) {
    const line = (y, label) =>
      `<line x1="0" y1="${y.toFixed(2)}" x2="${b.vbW}" y2="${y.toFixed(2)}" stroke="#94A3B8" stroke-width="0.6" stroke-dasharray="3 3" opacity="0.75"/>` +
      `<text x="${b.vbW - 2}" y="${(y - 1.6).toFixed(2)}" text-anchor="end" font-family="Consolas,monospace" font-size="5.5" fill="#94A3B8">${label}</text>`;
    return `<g class="wm-grid">${line(capTop, "cap " + capTop.toFixed(1))}${line(xTop, "x-height " + xTop.toFixed(1))}${line(B, "baseline " + B)}</g>`;
  }

  function wordmarkSvg(brand, opts = {}) {
    const b = brand === "video" ? VIDEO : FILM;
    const dark = !!opts.dark, mono = opts.mono || null;
    const ink = mono || (dark ? b.inkDark : b.inkLight);
    const mark = markInner(brand, mono);
    let text, defs = "";
    if (brand === "video") {
      /* 沿用 ChangoVideo 现有字标语义：整体 700、单色墨 */
      text = `<text x="${b.textX}" y="${B}" font-family="${b.font}" font-size="${F}" font-weight="700" letter-spacing="-1" fill="${ink}">hangoVideo</text>`;
    } else {
      /* 沿用 ChangoFilm 现有字标语义：hango 600 + Film 800 渐变（浅底品红实色） */
      let filmFill = ink;
      if (!mono) {
        if (dark) {
          defs = `<linearGradient id="cf-lk" gradientUnits="userSpaceOnUse" x1="216" y1="50" x2="334" y2="50"><stop offset="0" stop-color="${FILM.grad[0]}"/><stop offset="1" stop-color="${FILM.grad[1]}"/></linearGradient>`;
          filmFill = "url(#cf-lk)";
        } else filmFill = "#C026D3";
      }
      text = `<text x="${b.textX}" y="${B}" font-family="${b.font}" font-size="${F}" font-weight="600" fill="${ink}">hango<tspan font-weight="800" fill="${filmFill}">Film</tspan></text>`;
    }
    const grid = opts.grid ? gridOverlay(b) : "";
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${b.vbW} 100" role="img" aria-label="${b.name}"><defs>${defs}</defs>` +
      `<g transform="translate(${b.tx.toFixed(3)} ${b.ty.toFixed(3)}) scale(${b.s.toFixed(5)})">${mark}</g>${text}${grid}</svg>`;
  }

  const api = { F, B, capTop, xTop, VIDEO, FILM, markInner, wordmarkSvg, gridOverlay };
  root.WORDMARK = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);