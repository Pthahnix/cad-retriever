import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const html = readFileSync(new URL("../dist/index.html", import.meta.url), "utf-8");

// Also read all linked CSS from dist/_astro/ to check palette
const distDir = fileURLToPath(new URL("../dist/_astro", import.meta.url));
// Guard: Astro may inline small CSS; if no _astro dir exists, fall back to html-only check
const cssFiles = existsSync(distDir) ? readdirSync(distDir).filter(f => f.endsWith(".css")) : [];
const allCss = cssFiles.map(f => readFileSync(path.join(distDir, f), "utf-8")).join("\n");

test("deck has exactly 5 sections", () => {
  const matches = html.match(/class="[^"]*deck-section[^"]*"/g) ?? [];
  assert.equal(matches.length, 5);
});
test("demo slide embeds 5 model cards", () => {
  const matches = html.match(/class="[^"]*model-card[^"]*"/g) ?? [];
  assert.equal(matches.length, 5);
});
test("uses the cyberpunk palette, not the old green", () => {
  const combined = html + allCss;
  // Vite lowercases hex during minify, so check both cases
  assert.ok(combined.includes("#0D6E78") || combined.includes("0D6E78") || combined.includes("#0d6e78") || combined.includes("0d6e78"));
  assert.ok(!/#2a7\b/i.test(combined));
});
