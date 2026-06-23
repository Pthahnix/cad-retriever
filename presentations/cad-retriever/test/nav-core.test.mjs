import { test } from "node:test";
import assert from "node:assert/strict";
import { atEdge, nextIndex, shouldSuppressKeys } from "../src/scripts/nav-core.ts";

test("atEdge: at bottom going down is an edge", () => {
  assert.equal(atEdge(540, 1000, 460, 1), true);   // 540+460=1000
});
test("atEdge: mid-scroll going down is not an edge", () => {
  assert.equal(atEdge(200, 1000, 460, 1), false);
});
test("atEdge: at top going up is an edge", () => {
  assert.equal(atEdge(0, 1000, 460, -1), true);
});
test("atEdge: not at top going up is not an edge", () => {
  assert.equal(atEdge(50, 1000, 460, -1), false);
});
test("atEdge: short section (no scroll) is an edge both ways", () => {
  assert.equal(atEdge(0, 460, 460, 1), true);
  assert.equal(atEdge(0, 460, 460, -1), true);
});
test("nextIndex clamps at ends", () => {
  assert.equal(nextIndex(0, -1, 5), 0);
  assert.equal(nextIndex(4, 1, 5), 4);
  assert.equal(nextIndex(2, 1, 5), 3);
});
test("shouldSuppressKeys: input focus and modal", () => {
  assert.equal(shouldSuppressKeys({ tagName: "INPUT" }, false), true);
  assert.equal(shouldSuppressKeys({ tagName: "TEXTAREA" }, false), true);
  assert.equal(shouldSuppressKeys({ tagName: "DIV" }, false), false);
  assert.equal(shouldSuppressKeys(null, true), true);
  assert.equal(shouldSuppressKeys(null, false), false);
});
