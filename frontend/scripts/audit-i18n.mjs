// i18n key audit: verifies every t("...") literal in frontend/src against the
// synced zh/en packs (frontend/src/i18n/*.json, flattened from
// webui/i18n/{zh,en}.json). Template keys like t(`Backup Source ${slot}`) are
// checked as prefixes. Exits non-zero when gaps are found so it can gate CI.
// Usage: node frontend/scripts/audit-i18n.mjs
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = resolve(here, "..", "src");

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name)) out.push(full);
  }
  return out;
}

const packs = {};
for (const lang of ["zh", "en"]) {
  packs[lang] = JSON.parse(
    readFileSync(resolve(srcDir, "i18n", `${lang}.json`), "utf8")
  );
}

const files = walk(srcDir).filter(
  (f) => !f.includes(join("src", "i18n")) && !f.endsWith(".d.ts")
);

const literal = /(?<![.\w])t\(\s*"([^"]+)"|(?<![.\w])t\(\s*'([^']+)'/g;
const template = /(?<![.\w])t\(\s*`([^`]+)`/g;

const missing = { zh: new Map(), en: new Map() };
const prefixMissing = [];

function note(lang, key, file) {
  if (!(key in packs[lang])) {
    if (!missing[lang].has(key)) missing[lang].set(key, new Set());
    missing[lang].get(key).add(file);
  }
}

for (const file of files) {
  const text = readFileSync(file, "utf8");
  const rel = file.slice(srcDir.length + 1);
  for (const m of text.matchAll(literal)) {
    const key = m[1] ?? m[2];
    note("zh", key, rel);
    note("en", key, rel);
  }
  for (const m of text.matchAll(template)) {
    const key = m[1];
    if (!key.includes("${")) continue;
    const prefix = key.split("${")[0];
    const has = Object.keys(packs.zh).some((k) => k.startsWith(prefix));
    if (!has) prefixMissing.push(`${rel}: ${key}`);
  }
}

const zhMiss = [...missing.zh.keys()];
const enMiss = [...missing.en.keys()];

if (zhMiss.length) {
  console.log(`== missing in zh (${zhMiss.length}) ==`);
  for (const key of zhMiss)
    console.log(`  ${key}  <-  ${[...missing.zh.get(key)].join(", ")}`);
}
if (enMiss.length) {
  console.log(`== missing in en (${enMiss.length}) ==`);
  for (const key of enMiss)
    console.log(`  ${key}  <-  ${[...missing.en.get(key)].join(", ")}`);
}
if (prefixMissing.length) {
  console.log(`== unresolved template prefixes (${prefixMissing.length}) ==`);
  for (const line of prefixMissing) console.log(`  ${line}`);
}
if (!zhMiss.length && !enMiss.length && !prefixMissing.length) {
  console.log(`i18n audit OK: ${files.length} files, no missing keys`);
} else {
  process.exitCode = 1;
}
