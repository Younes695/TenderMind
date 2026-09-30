// Lists t("...") keys used in src/ that have no Arabic entry in src/i18n/ar/*.js.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, sep } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../src", import.meta.url));
const ar = {};
for (const f of readdirSync(join(root, "i18n", "ar"))) {
  const mod = await import(pathToFileURL(join(root, "i18n", "ar", f)).href);
  Object.assign(ar, mod.default);
}
const used = new Map();
function* walk(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) { if (n !== "__tests__") yield* walk(p); }
    else if (/\.jsx?$/.test(n)) yield p;
  }
}
for (const f of walk(root)) {
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(/\bt\(\s*"((?:[^"\\]|\\.)*)"/g)) {
    const key = m[1].split("\\n").join("\n").split('\\"').join('"');
    if (!used.has(key)) used.set(key, f.split(sep).pop());
  }
}
const missing = [...used].filter(([k]) => !(k in ar));
console.log(`keys used: ${used.size}, arabic entries: ${Object.keys(ar).length}, missing: ${missing.length}`);
for (const [k, f] of missing.slice(0, 80)) console.log(`  [${f}] ${k.slice(0, 90)}`);
