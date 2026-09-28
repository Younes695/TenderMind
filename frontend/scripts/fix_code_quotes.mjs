// Repairs curly quotes that ended up as JS string delimiters (a bulk edit turned
// " into “ ” and ' into ‘ ’). Only the character esbuild reports at the exact
// syntax-error position is replaced, repeated until the file parses, so curly
// quotes that belong inside string text are left alone.
import { transform } from "esbuild";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const SWAP = { "“": '"', "”": '"', "‘": "'", "’": "'" };

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (/\.(jsx?|mjs)$/.test(name)) yield p;
  }
}

function offsetOf(src, line, col) {
  const lines = src.split("\n");
  let off = 0;
  for (let i = 0; i < line - 1; i++) off += lines[i].length + 1;
  return off + col;
}

let fixedFiles = 0;
let broken = [];
for (const file of walk(new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"))) {
  let src = readFileSync(file, "utf8");
  let changes = 0;
  for (let guard = 0; guard < 2000; guard++) {
    try {
      await transform(src, { loader: "jsx", jsx: "automatic" });
      break;
    } catch (e) {
      const loc = e.errors?.[0]?.location;
      if (!loc) { broken.push(file); break; }
      const off = offsetOf(src, loc.line, loc.column);
      // the offending quote is at the error position or just before it
      let hit = -1;
      for (const o of [off, off - 1, off + 1]) if (SWAP[src[o]]) { hit = o; break; }
      if (hit < 0) {
        const lineText = src.split("\n")[loc.line - 1] || "";
        const idx = [...lineText].findIndex((ch) => SWAP[ch]);
        if (idx < 0) { broken.push(`${file}:${loc.line}:${loc.column} ${e.errors[0].text}`); break; }
        hit = offsetOf(src, loc.line, 0) + idx;
      }
      src = src.slice(0, hit) + SWAP[src[hit]] + src.slice(hit + 1);
      changes++;
    }
  }
  if (changes) { writeFileSync(file, src, "utf8"); fixedFiles++; console.log(`fixed ${changes} quote(s): ${file}`); }
}
console.log(`files repaired: ${fixedFiles}`);
if (broken.length) { console.log("still broken:"); broken.forEach((b) => console.log("  " + b)); process.exitCode = 1; }
