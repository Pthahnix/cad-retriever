import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/styles/global.css", import.meta.url), "utf-8");

test("global.css uses the cyberpunk palette, not the old green #2a7", () => {
  assert.ok(css.includes("#0D6E78"), "expected teal --teal #0D6E78");
  assert.ok(css.includes("#F5A800"), "expected amber --amber #F5A800");
  assert.ok(css.includes("#0A1A2E"), "expected navy --navy #0A1A2E");
  assert.ok(!/#2a7\b/i.test(css), "old green #2a7 should be gone");
});
