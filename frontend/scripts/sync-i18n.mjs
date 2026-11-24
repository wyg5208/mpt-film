// i18n sync (migration Part 2 / Part 6): flattens webui/i18n/{zh,en}.json
// ("Translation" nested object) into frontend/src/i18n/{lang}.json. Only the
// Chinese and English packs are kept — the other 12 locales were removed by
// request (webui/i18n itself still ships them for the legacy Streamlit UI).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SYNC_LANGS = ["zh", "en"];

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = resolve(here, "..", "..", "webui", "i18n");
const outDir = resolve(here, "..", "src", "i18n");

function flatten(obj, prefix, out) {
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      flatten(value, path, out);
    } else {
      out[path] = value;
    }
  }
  return out;
}

mkdirSync(outDir, { recursive: true });
let count = 0;
for (const lang of SYNC_LANGS) {
  const file = `${lang}.json`;
  const raw = JSON.parse(readFileSync(resolve(srcDir, file), "utf8"));
  const translation = raw.Translation ?? raw;
  const flat = flatten(translation, "", {});
  writeFileSync(
    resolve(outDir, file),
    JSON.stringify({ __lang: lang, ...flat }, null, 0) + "\n",
    "utf8"
  );
  count += 1;
  console.log(`i18n: ${lang} -> ${Object.keys(flat).length} keys`);
}
console.log(`synced ${count} language packs -> ${outDir}`);
