import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("built page renders exactly 5 model cards", () => {
  const html = readFileSync(new URL("../dist/index.html", import.meta.url), "utf-8");
  const matches = html.match(/class="[^"]*model-card[^"]*"/g) ?? [];
  assert.equal(matches.length, 5);
});
