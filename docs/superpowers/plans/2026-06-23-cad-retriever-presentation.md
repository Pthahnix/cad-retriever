# CAD Retriever Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Astro presentation with PPT-style page-flip + long-scroll sections, where one slide natively embeds the live (restyled) CAD Retriever web app, and restyle the existing `web/` app to a shared lo-fi cyberpunk palette.

**Architecture:** Single-page Astro app with 5 vertically-stacked full-screen `<section>`s. Each section scrolls its own overflow; arrow/PageUp-Down/Space flip between sections via `translateY`; wheel past a scroll boundary auto-flips. The demo slide reuses the web app's Astro components and TS scripts, scoped under `#demo-slide`. A shared palette lands in both `web/src/styles/global.css` and the deck's `webapp.css`.

**Tech Stack:** Astro ^7.0.0, three ^0.184.0, TypeScript, vanilla CSS, node:test for checks. Node >= 22.12.0.

## Global Constraints

- Node engine: `>=22.12.0` (copy verbatim into `package.json`).
- `astro` version: `^7.0.0`. `three` version: `^0.184.0`. `@types/three`: `^0.184.1`. No other runtime dependencies.
- Dev server runs in background per `web/CLAUDE.md`: `astro dev --background`; manage with `astro dev stop|status|logs`.
- Palette CSS variables (define once at `:root`, used by both deck and webapp):
  `--teal:#0D6E78; --rust:#C8300A; --amber:#F5A800; --dark-green:#1A4D3C; --mid-green:#2E6B4F; --navy:#0A1A2E`.
- Language: mixed — English titles, Chinese body, technical terms (InfoNCE, ControlNet, FAISS, STEP, Qwen3.6-27B) kept in original.
- Numbers not grounded in `context/2026-06-10-21-36-cost-estimate.md` (backend latency, post-filter eligible count) MUST be labeled "target" / "illustrative", never stated as measured fact.
- Web app stays cosmetic: hardcoded 5 demo models, fake 450ms latency. No backend.
- All `.astro` component `<script src="...">` paths are relative to the component file.
- The presentation is a NEW project at `presentations/cad-retriever/`. Do not break the existing `web/` project except the deliberate restyle in Task 2.

---

### Task 1: Scaffold the presentation Astro project

**Files:**
- Create: `presentations/cad-retriever/package.json`
- Create: `presentations/cad-retriever/astro.config.mjs`
- Create: `presentations/cad-retriever/tsconfig.json`
- Create: `presentations/cad-retriever/.gitignore`
- Create: `presentations/cad-retriever/src/pages/index.astro` (temporary smoke page, replaced in Task 8)

**Interfaces:**
- Produces: a buildable Astro project. `npm run build` emits `dist/index.html`.

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "cad-retriever-presentation",
  "type": "module",
  "version": "0.0.1",
  "engines": { "node": ">=22.12.0" },
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "astro": "astro",
    "test": "node --test"
  },
  "dependencies": {
    "astro": "^7.0.0",
    "three": "^0.184.0"
  },
  "devDependencies": {
    "@types/three": "^0.184.1"
  }
}
```

- [ ] **Step 2: Create `astro.config.mjs`**

```js
// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({});
```

- [ ] **Step 3: Create `tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict",
  "include": [".astro/types.d.ts", "**/*"],
  "exclude": ["dist"]
}
```

- [ ] **Step 4: Create `.gitignore`**

```
dist/
node_modules/
.astro/
```

- [ ] **Step 5: Create temporary smoke page `src/pages/index.astro`**

```astro
---
---
<html lang="en">
  <head><meta charset="utf-8" /><title>CAD Retriever — Deck</title></head>
  <body><p>scaffold ok</p></body>
</html>
```

- [ ] **Step 6: Install dependencies**

Run (from `presentations/cad-retriever/`): `npm install`
Expected: dependencies install, `node_modules/` created, no error.

- [ ] **Step 7: Build to verify scaffold**

Run: `npm run build`
Expected: build succeeds, `dist/index.html` exists containing `scaffold ok`.

- [ ] **Step 8: Commit**

```bash
git add presentations/cad-retriever/package.json presentations/cad-retriever/astro.config.mjs presentations/cad-retriever/tsconfig.json presentations/cad-retriever/.gitignore presentations/cad-retriever/src/pages/index.astro
git commit -m "feat(deck): scaffold CAD Retriever presentation Astro project"
```

---

### Task 2: Restyle the existing `web/` app to the shared palette

**Files:**
- Modify: `web/src/styles/global.css` (full replace)
- Test: `web/test/palette.test.mjs` (create)

**Interfaces:**
- Produces: the canonical restyled web-app CSS. Task 7 copies this same restyle (scoped) into the deck. Class names are unchanged: `.topbar`, `.searchbox`, `.upload-btn`, `.divider`, `.mode-tag`, `.go-btn`, `.attach`, `.status`, `.results`, `.score`, `.flag`, `.dash`, `.thumb`, `.modal`, `.modal-backdrop`, `.modal-body`, `.modal-close`, `.viewer-canvas`, `.viewer-caption`, `.viewer-meta`.

- [ ] **Step 1: Write the failing test `web/test/palette.test.mjs`**

```js
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `node --test test/palette.test.mjs`
Expected: FAIL — current `global.css` still has `#2a7` and lacks the new palette.

- [ ] **Step 3: Replace `web/src/styles/global.css` (full file)**

```css
:root {
  --teal: #0D6E78; --rust: #C8300A; --amber: #F5A800;
  --dark-green: #1A4D3C; --mid-green: #2E6B4F; --navy: #0A1A2E;
  --panel: #0f2236; --line: #1e3a52; --text: #dfe8ee; --muted: #8aa3b5;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  color: var(--text); background: var(--navy);
}
body {
  margin: 0 auto; padding: 2rem; max-width: 1000px;
  background:
    radial-gradient(120% 80% at 0% 0%, rgba(13,110,120,.25), transparent 60%),
    radial-gradient(120% 80% at 100% 100%, rgba(200,48,10,.18), transparent 55%),
    var(--navy);
  min-height: 100vh;
}

/* ---------- search bar ---------- */
.topbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.25rem; }
.topbar h1 { font-size: 1.2rem; margin: 0; white-space: nowrap; color: var(--text); }
.searchbox {
  flex: 1; display: flex; gap: .4rem; align-items: center;
  border: 1px solid var(--line); border-radius: 8px; padding: .3rem .3rem .3rem .7rem;
  background: rgba(255,255,255,.03);
}
.searchbox:focus-within { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(13,110,120,.25); }
.searchbox input[type="text"] { flex: 1; border: none; font: inherit; outline: none; background: none; color: var(--text); }
.searchbox input[type="text"]::placeholder { color: var(--muted); }

.upload-btn {
  display: grid; place-items: center; width: 30px; height: 30px;
  border: none; background: none; border-radius: 6px; cursor: pointer; color: var(--muted);
}
.upload-btn:hover { background: rgba(13,110,120,.18); color: var(--teal); }
.upload-btn svg { width: 18px; height: 18px; }
.divider { width: 1px; align-self: stretch; background: var(--line); margin: .15rem .1rem; }

.mode-tag { font-size: .72rem; color: var(--muted); padding: 0 .4rem; white-space: nowrap; }
.go-btn { font: inherit; background: var(--teal); color: #fff; border: none; border-radius: 6px; padding: .4rem 1rem; cursor: pointer; transition: background .15s; }
.go-btn:hover { background: var(--rust); }

.attach { display: none; align-items: center; gap: .4rem; margin-bottom: 1rem; font-size: .8rem; color: var(--muted); }
.attach.show { display: flex; }
.attach img { width: 36px; height: 36px; object-fit: cover; border-radius: 6px; border: 1px solid var(--teal); }
.attach .x { border: none; background: none; cursor: pointer; color: var(--rust); font-size: 1rem; line-height: 1; }

.status { color: var(--amber); font-size: 0.85rem; margin: 0 0 1rem; }

/* ---------- results table ---------- */
.results { width: 100%; border-collapse: collapse; font-size: .85rem; transition: opacity 0.2s; }
.results thead tr { text-align: left; color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; border-bottom: 2px solid var(--line); }
.results th { padding: .6rem .5rem; }
.results tbody tr { border-bottom: 1px solid var(--line); cursor: pointer; }
.results tbody tr:hover { background: rgba(13,110,120,.12); }
.results td { padding: .45rem .5rem; }
.score { font-weight: 700; color: var(--amber); }
.flag { font-size: .7rem; background: rgba(200,48,10,.18); color: var(--rust); border-radius: 4px; padding: .1rem .45rem; }
.dash { color: var(--muted); }

/* ---------- thumbnails ---------- */
.thumb { width: 48px; height: 48px; border-radius: 6px; background: var(--panel); object-fit: contain; display: block; border: 1px solid var(--line); }

/* ---------- viewer modal ---------- */
.modal { position: fixed; inset: 0; display: grid; place-items: center; z-index: 10; }
.modal[hidden] { display: none; }
.modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.65); }
.modal-body { position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 1.25rem; max-width: 560px; width: 90%; }
.modal-close { position: absolute; top: 0.5rem; right: 0.75rem; border: none; background: none; font-size: 1.5rem; cursor: pointer; color: var(--text); }
.viewer-canvas { width: 100%; min-height: 360px; background: #0b1b2b; border-radius: 6px; border: 1px solid var(--teal); }
.viewer-caption { margin: 0.75rem 0 0.5rem; font-size: 0.95rem; color: var(--text); }
.viewer-meta { display: flex; gap: 0.5rem; font-size: 0.75rem; color: var(--muted); }
.viewer-meta span { background: rgba(13,110,120,.18); color: var(--teal); border-radius: 999px; padding: 0.1rem 0.6rem; }
```

- [ ] **Step 4: Update the viewer canvas background in `web/src/scripts/viewer.ts`**

The scene background is hardcoded light (`0xf4f6f8`). Change line 43 to match the dark canvas.

Find: `scene.background = new THREE.Color(0xf4f6f8);`
Replace: `scene.background = new THREE.Color(0x0b1b2b);`

- [ ] **Step 5: Run the palette test**

Run (from `web/`): `node --test test/palette.test.mjs`
Expected: PASS.

- [ ] **Step 6: Build web to confirm nothing broke**

Run (from `web/`): `npm run build && node --test test/grid.test.mjs`
Expected: build succeeds; existing grid test still passes (5 model cards).

- [ ] **Step 7: Commit**

```bash
git add web/src/styles/global.css web/src/scripts/viewer.ts web/test/palette.test.mjs
git commit -m "feat(web): restyle app to lo-fi cyberpunk palette"
```

---

### Task 3: Deck navigation — boundary logic (pure, tested) + DOM wiring

**Files:**
- Create: `presentations/cad-retriever/src/scripts/nav-core.ts` (pure logic, unit-tested)
- Create: `presentations/cad-retriever/src/scripts/deck-nav.ts` (DOM wiring, uses nav-core)
- Test: `presentations/cad-retriever/test/nav-core.test.mjs`

**Interfaces:**
- Produces from `nav-core.ts`:
  - `atEdge(scrollTop: number, scrollHeight: number, clientHeight: number, dir: 1 | -1): boolean` — true if a section scrolled to `scrollTop` is at the edge in flip direction `dir` (1 = down/next, -1 = up/prev). Uses a 2px tolerance.
  - `nextIndex(current: number, dir: 1 | -1, count: number): number` — clamps to `[0, count-1]`.
  - `shouldSuppressKeys(active: Element | null, modalOpen: boolean): boolean` — true when `active` is an `INPUT`/`TEXTAREA` or `modalOpen` is true.
- Produces from `deck-nav.ts`: side effects only — wires keyboard, wheel, touch, progress indicator to `.deck-section` elements. No exports consumed elsewhere.

- [ ] **Step 1: Write the failing test `test/nav-core.test.mjs`**

```js
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `presentations/cad-retriever/`): `node --test test/nav-core.test.mjs`
Expected: FAIL — `nav-core.ts` does not exist.
(Note: `node --test` runs `.ts` via Node 22's type-stripping; if the runner cannot import `.ts`, rename the import target to a `.mjs` re-export — but Node >=22.12 strips types, so `.ts` import works.)

- [ ] **Step 3: Write `src/scripts/nav-core.ts`**

```ts
// Pure navigation helpers — no DOM, unit-testable.
const TOL = 2; // px tolerance for "at edge"

export function atEdge(scrollTop: number, scrollHeight: number, clientHeight: number, dir: 1 | -1): boolean {
  if (dir === 1) return scrollTop + clientHeight >= scrollHeight - TOL;
  return scrollTop <= TOL;
}

export function nextIndex(current: number, dir: 1 | -1, count: number): number {
  return Math.max(0, Math.min(count - 1, current + dir));
}

export function shouldSuppressKeys(active: { tagName: string } | null, modalOpen: boolean): boolean {
  if (modalOpen) return true;
  if (!active) return false;
  return active.tagName === "INPUT" || active.tagName === "TEXTAREA";
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test test/nav-core.test.mjs`
Expected: PASS (all 7 tests).

- [ ] **Step 5: Write `src/scripts/deck-nav.ts` (DOM wiring)**

```ts
import { atEdge, nextIndex, shouldSuppressKeys } from "./nav-core";

const track = document.querySelector<HTMLElement>("#deck-track")!;
const sections = Array.from(document.querySelectorAll<HTMLElement>(".deck-section"));
const indicator = document.querySelector<HTMLElement>("#deck-progress")!;
const count = sections.length;
let current = 0;
let animating = false;

// modalOpen is read from a data attribute the demo viewer toggles.
const isModalOpen = () => document.body.dataset.modalOpen === "1";

function go(dir: 1 | -1) {
  const target = nextIndex(current, dir, count);
  if (target === current) return;
  current = target;
  animating = true;
  track.style.transform = `translateY(-${current * 100}vh)`;
  indicator.textContent = `${current + 1} / ${count}`;
  // re-enable input after the CSS transition (matches .deck-track transition: 600ms)
  window.setTimeout(() => { animating = false; }, 650);
}

// Keyboard: explicit flip keys always flip (when not suppressed).
window.addEventListener("keydown", (e) => {
  if (shouldSuppressKeys(document.activeElement, isModalOpen())) return;
  if (e.key === "ArrowDown" || e.key === "PageDown" || e.key === " ") { e.preventDefault(); go(1); }
  else if (e.key === "ArrowUp" || e.key === "PageUp") { e.preventDefault(); go(-1); }
  else if (e.key === "Home") { e.preventDefault(); while (current > 0) go(-1); }
  else if (e.key === "End") { e.preventDefault(); while (current < count - 1) go(1); }
});

// Wheel: scroll within section; flip only when at boundary and pushing past it.
let wheelLock = 0;
window.addEventListener("wheel", (e) => {
  if (isModalOpen() || animating) return;
  const sec = sections[current];
  const dir: 1 | -1 = e.deltaY > 0 ? 1 : -1;
  if (atEdge(sec.scrollTop, sec.scrollHeight, sec.clientHeight, dir)) {
    const now = e.timeStamp;
    if (now - wheelLock < 700) return;     // throttle: one flip per gesture
    wheelLock = now;
    e.preventDefault();
    go(dir);
  }
  // else: let the section scroll natively (do not preventDefault)
}, { passive: false });

// Touch: flip on swipe when at boundary.
let touchStartY = 0;
window.addEventListener("touchstart", (e) => { touchStartY = e.touches[0].clientY; }, { passive: true });
window.addEventListener("touchend", (e) => {
  if (isModalOpen() || animating) return;
  const dy = touchStartY - e.changedTouches[0].clientY;
  if (Math.abs(dy) < 40) return;
  const dir: 1 | -1 = dy > 0 ? 1 : -1;
  const sec = sections[current];
  if (atEdge(sec.scrollTop, sec.scrollHeight, sec.clientHeight, dir)) go(dir);
});

indicator.textContent = `1 / ${count}`;
```

- [ ] **Step 6: Commit**

```bash
git add presentations/cad-retriever/src/scripts/nav-core.ts presentations/cad-retriever/src/scripts/deck-nav.ts presentations/cad-retriever/test/nav-core.test.mjs
git commit -m "feat(deck): navigation core logic + DOM wiring with boundary auto-flip"
```

---

### Task 4: Deck layout + deck CSS (section-stacking skeleton)

**Files:**
- Create: `presentations/cad-retriever/src/styles/deck.css`
- Create: `presentations/cad-retriever/src/layouts/Deck.astro`

**Interfaces:**
- Consumes: `deck-nav.ts` (Task 3) by including it via `<script>`.
- Produces: `Deck.astro` default-slot layout. Expects its slotted children to be `<section class="deck-section">…</section>` blocks. Renders `#deck-track` (the translated stack), `#deck-progress` (indicator). Used by `index.astro` (Task 8).

- [ ] **Step 1: Create `src/styles/deck.css`**

```css
:root {
  --teal: #0D6E78; --rust: #C8300A; --amber: #F5A800;
  --dark-green: #1A4D3C; --mid-green: #2E6B4F; --navy: #0A1A2E;
  --panel: #0f2236; --line: #1e3a52; --text: #e6eef3; --muted: #93a7b6;
  --font-serif: "DM Serif Display", "Playfair Display", Georgia, serif;
  --font-sans: "Noto Sans SC", system-ui, -apple-system, "Segoe UI", sans-serif;
}
* , *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--navy); color: var(--text); font-family: var(--font-sans); }

#deck-track { transition: transform 600ms cubic-bezier(.7,0,.2,1); will-change: transform; }
.deck-section {
  height: 100vh; width: 100vw; overflow-y: auto; overflow-x: hidden;
  padding: 4rem clamp(1.5rem, 6vw, 7rem);
  scrollbar-width: thin; scrollbar-color: var(--teal) transparent;
}
/* subtle noise + diagonal wash; each slide can override --wash-a/--wash-b */
.deck-section {
  --wash-a: rgba(13,110,120,.30); --wash-b: rgba(200,48,10,.18);
  background:
    radial-gradient(100% 70% at 0% 0%, var(--wash-a), transparent 60%),
    radial-gradient(90% 70% at 100% 100%, var(--wash-b), transparent 55%),
    var(--navy);
}

#deck-progress {
  position: fixed; bottom: 1rem; right: 1.25rem; z-index: 50;
  font-family: var(--font-sans); font-size: .8rem; letter-spacing: .08em;
  color: var(--amber); background: rgba(10,26,46,.7);
  border: 1px solid var(--line); border-radius: 999px; padding: .25rem .8rem;
}
#deck-hint {
  position: fixed; bottom: 1rem; left: 1.25rem; z-index: 50;
  font-size: .72rem; color: var(--muted);
}

/* typography */
.eyebrow { display: inline-block; font-size: .7rem; letter-spacing: .18em; text-transform: uppercase;
  color: var(--amber); border: 1px solid var(--amber); border-radius: 999px; padding: .2rem .7rem; }
.display { font-family: var(--font-serif); font-style: italic; font-size: clamp(2.4rem, 6vw, 4.5rem); line-height: 1.05; margin: 1rem 0; }
h2.section-title { font-family: var(--font-serif); font-size: clamp(1.6rem, 3.5vw, 2.6rem); margin: 0 0 1rem; }
h3 { font-size: 1.15rem; margin: 1.5rem 0 .5rem; color: var(--amber); }
p, li { font-size: 1.02rem; line-height: 1.75; color: var(--text); }
.muted { color: var(--muted); }
a { color: var(--teal); }

/* print: stack everything */
@media print {
  html, body { overflow: visible; height: auto; }
  #deck-track { transform: none !important; }
  .deck-section { height: auto; min-height: 100vh; page-break-after: always; }
  #deck-progress, #deck-hint { display: none; }
}
```

- [ ] **Step 2: Create `src/layouts/Deck.astro`**

```astro
---
import "../styles/deck.css";
import "../styles/figures.css";
interface Props { title?: string; }
const { title = "CAD Retriever" } = Astro.props;
---
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="deck-track">
      <slot />
    </div>
    <div id="deck-progress">1 / 5</div>
    <div id="deck-hint">↑ ↓ / PgUp PgDn 翻页 · 滚动到边界自动翻页</div>
    <script src="../scripts/deck-nav.ts"></script>
  </body>
</html>
```

- [ ] **Step 3: Create an empty `src/styles/figures.css` placeholder (filled in Task 6)**

```css
/* figure / diagram styling — populated in Task 6 */
```

- [ ] **Step 4: Build to verify the layout compiles**

Temporarily ensure `index.astro` still builds (Task 1 smoke page is fine). Run (from `presentations/cad-retriever/`): `npm run build`
Expected: build succeeds. (Deck.astro is not yet used by a page; this step only confirms it parses — Astro compiles layouts when imported, so this is verified fully in Task 8. For now confirm no syntax error by importing it in the smoke page is optional.)

- [ ] **Step 5: Commit**

```bash
git add presentations/cad-retriever/src/styles/deck.css presentations/cad-retriever/src/layouts/Deck.astro presentations/cad-retriever/src/styles/figures.css
git commit -m "feat(deck): Deck layout + theme CSS (stacked sections, progress, print)"
```

---

### Task 5: Reusable deck UI primitives

**Files:**
- Create: `presentations/cad-retriever/src/components/ui/Pill.astro`
- Create: `presentations/cad-retriever/src/components/ui/Card.astro`
- Create: `presentations/cad-retriever/src/components/ui/CodeBlock.astro`
- Create: `presentations/cad-retriever/src/components/ui/StatBar.astro`

**Interfaces:**
- `Pill` props: `{ label: string }` → renders `<span class="eyebrow">{label}</span>` (slot also allowed).
- `Card` props: `{ accent?: "teal" | "rust" | "amber" }` (default `teal`) → soft-shadow rounded card wrapping its slot.
- `CodeBlock` props: `{ code: string; lang?: string }` → dark `<pre><code>` with teal left border. Renders `code` verbatim (no highlighting lib).
- `StatBar` props: `{ label: string; value: number; max: number; unit?: string; accent?: "teal"|"rust"|"amber" }` → labeled horizontal bar, width = `value/max`. Used in Slides 2 and 4.

- [ ] **Step 1: Create `Pill.astro`**

```astro
---
interface Props { label?: string; }
const { label } = Astro.props;
---
<span class="eyebrow">{label}<slot /></span>
```

- [ ] **Step 2: Create `Card.astro`**

```astro
---
interface Props { accent?: "teal" | "rust" | "amber"; }
const { accent = "teal" } = Astro.props;
const color = { teal: "var(--teal)", rust: "var(--rust)", amber: "var(--amber)" }[accent];
---
<div class="deck-card" style={`--card-accent:${color}`}>
  <slot />
</div>
<style>
  .deck-card {
    background: rgba(255,255,255,.03);
    border: 1px solid var(--line);
    border-top: 3px solid var(--card-accent);
    border-radius: 12px; padding: 1.25rem 1.4rem;
    box-shadow: 0 8px 30px rgba(0,0,0,.35);
  }
  .deck-card :global(h3) { margin-top: 0; }
</style>
```

- [ ] **Step 3: Create `CodeBlock.astro`**

```astro
---
interface Props { code: string; lang?: string; }
const { code, lang = "" } = Astro.props;
---
<pre class="deck-code" data-lang={lang}><code>{code}</code></pre>
<style>
  .deck-code {
    background: #08111d; border: 1px solid var(--line); border-left: 3px solid var(--teal);
    border-radius: 8px; padding: 1rem 1.1rem; overflow-x: auto;
    font-family: "Fira Code", Consolas, monospace; font-size: .85rem; line-height: 1.6;
    color: #cfe3ec;
  }
</style>
```

- [ ] **Step 4: Create `StatBar.astro`**

```astro
---
interface Props { label: string; value: number; max: number; unit?: string; accent?: "teal"|"rust"|"amber"; }
const { label, value, max, unit = "", accent = "teal" } = Astro.props;
const pct = Math.max(0, Math.min(100, (value / max) * 100));
const color = { teal: "var(--teal)", rust: "var(--rust)", amber: "var(--amber)" }[accent];
---
<div class="statbar">
  <div class="statbar-head"><span>{label}</span><span class="statbar-val">{value}{unit}</span></div>
  <div class="statbar-track"><div class="statbar-fill" style={`width:${pct}%;background:${color}`}></div></div>
</div>
<style>
  .statbar { margin: .6rem 0; }
  .statbar-head { display: flex; justify-content: space-between; font-size: .85rem; margin-bottom: .25rem; }
  .statbar-val { color: var(--amber); font-weight: 700; }
  .statbar-track { height: 10px; background: rgba(255,255,255,.06); border-radius: 999px; overflow: hidden; }
  .statbar-fill { height: 100%; border-radius: 999px; }
</style>
```

- [ ] **Step 5: Build to verify primitives compile**

These are not yet imported by a page; they compile when used in Task 6+. To verify now, temporarily import all four in the smoke `index.astro`, build, then revert — OR defer verification to Task 8. Recommended: defer (avoids churn). Mark this step done once the four files exist.

- [ ] **Step 6: Commit**

```bash
git add presentations/cad-retriever/src/components/ui/
git commit -m "feat(deck): reusable UI primitives (Pill, Card, CodeBlock, StatBar)"
```

---

### Task 6: Figure / diagram CSS

**Files:**
- Modify: `presentations/cad-retriever/src/styles/figures.css` (replace the Task 4 placeholder)

**Interfaces:**
- Produces named figure classes used by slide components (Tasks 8a–8d):
  - `.fig-grid` / `.fig-grid.cols-3` — responsive card grid.
  - `.flow` / `.flow-step` / `.flow-arrow` — horizontal pipeline with teal arrows.
  - `.data-table` — teal-bordered table.
  - `.funnel` / `.funnel-row` — quality-filter funnel (width set inline per row).
  - `.arch-layer` — stacked architecture layer block.
  - `.modality` / `.modality-converge` — three-modality → shared-space diagram.
  - `.pull-quote` — emphasized callout.
  - `.view-ring` / `.view-dot` — 30-view azimuth ring figure.

- [ ] **Step 1: Replace `src/styles/figures.css`**

```css
/* ---------- grids ---------- */
.fig-grid { display: grid; gap: 1rem; grid-template-columns: 1fr; margin: 1rem 0; }
@media (min-width: 720px) { .fig-grid.cols-2 { grid-template-columns: 1fr 1fr; }
  .fig-grid.cols-3 { grid-template-columns: repeat(3, 1fr); } }

/* ---------- horizontal flow / pipeline ---------- */
.flow { display: flex; flex-wrap: wrap; align-items: stretch; gap: .5rem; margin: 1.25rem 0; }
.flow-step { flex: 1 1 0; min-width: 130px; background: rgba(255,255,255,.03);
  border: 1px solid var(--line); border-radius: 10px; padding: .8rem .9rem; }
.flow-step .when { color: var(--amber); font-size: .8rem; font-weight: 700; }
.flow-arrow { align-self: center; color: var(--teal); font-size: 1.4rem; }

/* ---------- tables ---------- */
.data-table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .9rem; }
.data-table th, .data-table td { border: 1px solid var(--line); padding: .5rem .65rem; text-align: left; vertical-align: top; }
.data-table thead th { background: rgba(13,110,120,.18); color: var(--teal); text-transform: uppercase; font-size: .72rem; letter-spacing: .05em; }
.data-table code { background: rgba(200,48,10,.16); color: var(--rust); border-radius: 4px; padding: .05rem .35rem; }

/* ---------- funnel ---------- */
.funnel { margin: 1.25rem 0; }
.funnel-row { margin: .3rem auto; height: 2.4rem; display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: .85rem; border-radius: 6px;
  background: linear-gradient(90deg, var(--teal), var(--mid-green)); }
.funnel-row.illustrative { background: linear-gradient(90deg, var(--rust), var(--amber)); }

/* ---------- architecture layers ---------- */
.arch-layer { border: 1px solid var(--line); border-left: 4px solid var(--teal); border-radius: 8px;
  padding: .8rem 1rem; margin: .5rem 0; background: rgba(255,255,255,.03); }
.arch-layer .layer-name { color: var(--amber); font-weight: 700; }
.arch-sep { text-align: center; color: var(--teal); font-size: 1.2rem; }

/* ---------- three-modality converge ---------- */
.modality { display: grid; gap: .75rem; grid-template-columns: 1fr; align-items: center; }
@media (min-width: 720px) { .modality { grid-template-columns: 1fr auto 1fr auto 1fr; } }
.modality-converge { text-align: center; font-family: var(--font-serif); font-style: italic;
  color: var(--amber); border: 1px dashed var(--amber); border-radius: 12px; padding: 1rem; }

/* ---------- pull quote ---------- */
.pull-quote { border-left: 4px solid var(--rust); padding: .5rem 0 .5rem 1.1rem; margin: 1.25rem 0;
  font-family: var(--font-serif); font-style: italic; font-size: 1.25rem; color: var(--text); }

/* ---------- 30-view ring ---------- */
.view-ring { position: relative; width: 220px; height: 220px; margin: 1rem auto; border: 1px dashed var(--line); border-radius: 50%; }
.view-ring .center { position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); font-size: .8rem; }
.view-dot { position: absolute; width: 12px; height: 12px; border-radius: 50%; background: var(--teal);
  transform: translate(-50%, -50%); box-shadow: 0 0 8px var(--teal); }
.elev-legend { display: flex; gap: .75rem; justify-content: center; font-size: .8rem; color: var(--muted); }
.elev-legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: .3rem; vertical-align: middle; }
```

- [ ] **Step 2: Build to confirm CSS parses (no breakage)**

Run (from `presentations/cad-retriever/`): `npm run build`
Expected: build succeeds (CSS is imported by `Deck.astro`; if `Deck.astro` is not yet used, this verifies in Task 8 — for now confirm no file error).

- [ ] **Step 3: Commit**

```bash
git add presentations/cad-retriever/src/styles/figures.css
git commit -m "feat(deck): figure/diagram CSS (flow, funnel, arch, modality, view-ring)"
```

---

### Task 7: Copy the web app into the deck (components, scripts, data, scoped CSS)

**Files:**
- Create: `presentations/cad-retriever/src/data/models.json` (copy of `web/src/data/models.json`)
- Create: `presentations/cad-retriever/src/scripts/webapp/shapes.ts` (copy verbatim)
- Create: `presentations/cad-retriever/src/scripts/webapp/thumbs.ts` (copy verbatim)
- Create: `presentations/cad-retriever/src/scripts/webapp/search.ts` (copy verbatim)
- Create: `presentations/cad-retriever/src/scripts/webapp/viewer.ts` (copy + 2 edits)
- Create: `presentations/cad-retriever/src/components/webapp/SearchBar.astro`
- Create: `presentations/cad-retriever/src/components/webapp/ModelCard.astro` (copy verbatim)
- Create: `presentations/cad-retriever/src/components/webapp/ResultsGrid.astro`
- Create: `presentations/cad-retriever/src/components/webapp/ViewerModal.astro`
- Create: `presentations/cad-retriever/src/styles/webapp.css` (scoped restyle)

**Interfaces:**
- Consumes: `models.json` shape `{ id, caption, shape, score, probe:{ n_faces, n_solids, bbox_ratio, quality_flags } }`.
- Produces: `<SearchBar/>`, `<ResultsGrid/>`, `<ViewerModal/>` components rendered inside `#demo-slide` (Task 8d). Scripts target the same DOM ids as the originals: `#text-input`, `#search-btn`, `#status`, `.results`, `#mode-tag`, `#attach*`, `#viewer-modal`, `#viewer-canvas`, `.model-card`.

- [ ] **Step 1: Copy `models.json` verbatim**

Copy `web/src/data/models.json` → `presentations/cad-retriever/src/data/models.json` (exact contents — the 5 demo models).

- [ ] **Step 2: Copy `shapes.ts`, `thumbs.ts`, `search.ts` verbatim**

Copy these three from `web/src/scripts/` → `presentations/cad-retriever/src/scripts/webapp/` unchanged. Their relative imports (`./shapes`) and DOM queries remain valid in the new folder.

- [ ] **Step 3: Copy `viewer.ts` with 2 edits**

Copy `web/src/scripts/viewer.ts` → `presentations/cad-retriever/src/scripts/webapp/viewer.ts`, then make these edits:

Edit A — the data import path stays `../data/models.json`? No: in the deck it is two levels up. Change:
Find: `import models from "../data/models.json";`
Replace: `import models from "../../data/models.json";`

Edit B — set body modal flag so deck nav suppresses keys while the viewer is open. In `function open(model: Model)`, right after `modal.hidden = false;` add:
```ts
  document.body.dataset.modalOpen = "1";
```
And in `function close()`, right after `modal.hidden = true;` add:
```ts
  document.body.dataset.modalOpen = "0";
```
(Also update the canvas background to match the dark theme: ensure `scene.background = new THREE.Color(0x0b1b2b);` — already done in `web/` Task 2, keep it here too.)

- [ ] **Step 4: Copy `ModelCard.astro` verbatim**

Copy `web/src/components/ModelCard.astro` → `presentations/cad-retriever/src/components/webapp/ModelCard.astro` unchanged.

- [ ] **Step 5: Create `SearchBar.astro` (copy with fixed script path)**

Copy `web/src/components/SearchBar.astro`, but the final script tag must point at the webapp scripts folder. The markup is identical; only the script src changes.

Find: `<script src="../scripts/search.ts"></script>`
Replace: `<script src="../../scripts/webapp/search.ts"></script>`

- [ ] **Step 6: Create `ResultsGrid.astro` (copy with fixed paths)**

Copy `web/src/components/ResultsGrid.astro`, fix the two relative paths:

Find: `import models from "../data/models.json";`
Replace: `import models from "../../data/models.json";`

Find: `<script src="../scripts/thumbs.ts"></script>`
Replace: `<script src="../../scripts/webapp/thumbs.ts"></script>`

(The `import ModelCard from "./ModelCard.astro";` line stays — ModelCard is a sibling.)

- [ ] **Step 7: Create `ViewerModal.astro` (copy with fixed script path)**

Copy `web/src/components/ViewerModal.astro`, fix the script path:

Find: `<script src="../scripts/viewer.ts"></script>`
Replace: `<script src="../../scripts/webapp/viewer.ts"></script>`

- [ ] **Step 8: Create scoped `src/styles/webapp.css`**

This is the Task 2 `web/src/styles/global.css` body rules, each scoped under `#demo-slide`, with palette vars omitted (inherited from `deck.css`). The `:root` block is dropped; `body` rules become `#demo-slide`.

```css
/* Web-app styles, scoped so they never leak into deck chrome. */
#demo-slide { --panel:#0f2236; --line:#1e3a52; --muted:#8aa3b5; color: var(--text); }

#demo-slide .topbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.25rem; }
#demo-slide .topbar h1 { font-size: 1.2rem; margin: 0; white-space: nowrap; color: var(--text); }
#demo-slide .searchbox { flex: 1; display: flex; gap: .4rem; align-items: center;
  border: 1px solid var(--line); border-radius: 8px; padding: .3rem .3rem .3rem .7rem; background: rgba(255,255,255,.03); }
#demo-slide .searchbox:focus-within { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(13,110,120,.25); }
#demo-slide .searchbox input[type="text"] { flex: 1; border: none; font: inherit; outline: none; background: none; color: var(--text); }
#demo-slide .searchbox input[type="text"]::placeholder { color: var(--muted); }
#demo-slide .upload-btn { display: grid; place-items: center; width: 30px; height: 30px;
  border: none; background: none; border-radius: 6px; cursor: pointer; color: var(--muted); }
#demo-slide .upload-btn:hover { background: rgba(13,110,120,.18); color: var(--teal); }
#demo-slide .upload-btn svg { width: 18px; height: 18px; }
#demo-slide .divider { width: 1px; align-self: stretch; background: var(--line); margin: .15rem .1rem; }
#demo-slide .mode-tag { font-size: .72rem; color: var(--muted); padding: 0 .4rem; white-space: nowrap; }
#demo-slide .go-btn { font: inherit; background: var(--teal); color: #fff; border: none; border-radius: 6px; padding: .4rem 1rem; cursor: pointer; transition: background .15s; }
#demo-slide .go-btn:hover { background: var(--rust); }
#demo-slide .attach { display: none; align-items: center; gap: .4rem; margin-bottom: 1rem; font-size: .8rem; color: var(--muted); }
#demo-slide .attach.show { display: flex; }
#demo-slide .attach img { width: 36px; height: 36px; object-fit: cover; border-radius: 6px; border: 1px solid var(--teal); }
#demo-slide .attach .x { border: none; background: none; cursor: pointer; color: var(--rust); font-size: 1rem; line-height: 1; }
#demo-slide .status { color: var(--amber); font-size: 0.85rem; margin: 0 0 1rem; }
#demo-slide .results { width: 100%; border-collapse: collapse; font-size: .85rem; transition: opacity 0.2s; }
#demo-slide .results thead tr { text-align: left; color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; border-bottom: 2px solid var(--line); }
#demo-slide .results th { padding: .6rem .5rem; }
#demo-slide .results tbody tr { border-bottom: 1px solid var(--line); cursor: pointer; }
#demo-slide .results tbody tr:hover { background: rgba(13,110,120,.12); }
#demo-slide .results td { padding: .45rem .5rem; }
#demo-slide .score { font-weight: 700; color: var(--amber); }
#demo-slide .flag { font-size: .7rem; background: rgba(200,48,10,.18); color: var(--rust); border-radius: 4px; padding: .1rem .45rem; }
#demo-slide .dash { color: var(--muted); }
#demo-slide .thumb { width: 48px; height: 48px; border-radius: 6px; background: var(--panel); object-fit: contain; display: block; border: 1px solid var(--line); }

/* modal is fixed/full-viewport: scope by id but keep it above the deck */
.modal { position: fixed; inset: 0; display: grid; place-items: center; z-index: 100; }
.modal[hidden] { display: none; }
.modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.65); }
.modal-body { position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 1.25rem; max-width: 560px; width: 90%; }
.modal-close { position: absolute; top: 0.5rem; right: 0.75rem; border: none; background: none; font-size: 1.5rem; cursor: pointer; color: var(--text); }
.viewer-canvas { width: 100%; min-height: 360px; background: #0b1b2b; border-radius: 6px; border: 1px solid var(--teal); }
.viewer-caption { margin: 0.75rem 0 0.5rem; font-size: 0.95rem; color: var(--text); }
.viewer-meta { display: flex; gap: 0.5rem; font-size: 0.75rem; color: var(--muted); }
.viewer-meta span { background: rgba(13,110,120,.18); color: var(--teal); border-radius: 999px; padding: 0.1rem 0.6rem; }
```

Note: `.modal*` rules are intentionally NOT scoped under `#demo-slide` because the modal renders fixed over the whole viewport; `z-index:100` keeps it above `#deck-progress` (z-index 50).

- [ ] **Step 9: Commit**

```bash
git add presentations/cad-retriever/src/data presentations/cad-retriever/src/scripts/webapp presentations/cad-retriever/src/components/webapp presentations/cad-retriever/src/styles/webapp.css
git commit -m "feat(deck): import web app components/scripts into deck, scoped under #demo-slide"
```

---

### Task 8a: Slide 1 — Introduction & Problem Statement

**Files:**
- Create: `presentations/cad-retriever/src/components/slides/Slide1Intro.astro`

**Interfaces:**
- Consumes: `Pill`, `Card` from `../ui/`. Renders a `<section class="deck-section">`.
- Produces: `<Slide1Intro/>` used by `index.astro` (Task 9).

- [ ] **Step 1: Create `Slide1Intro.astro`**

```astro
---
import Pill from "../ui/Pill.astro";
import Card from "../ui/Card.astro";
---
<section class="deck-section" style="--wash-a:rgba(13,110,120,.38);--wash-b:rgba(245,168,0,.18)">
  <Pill label="Research Demo · 2026" />
  <h1 class="display">CAD Retriever</h1>
  <p style="font-size:1.3rem;max-width:48ch" class="muted">
    Multimodal Neural Search for Mechanical Parts —
    用<strong style="color:var(--text)">自然语言、草图、参考图</strong>检索语义相似的 CAD 零件。
  </p>

  <h2 class="section-title">三种输入，一个潜空间</h2>
  <div class="modality">
    <Card accent="teal"><h3>Text</h3><p class="muted">"a flat cylindrical disc with mounting holes"</p></Card>
    <div class="arch-sep">→</div>
    <div class="modality-converge">Shared<br/>Embedding<br/>Space</div>
    <div class="arch-sep">←</div>
    <Card accent="amber"><h3>Image</h3><p class="muted">参考照片 / 渲染视图</p></Card>
  </div>
  <div class="fig-grid cols-3" style="margin-top:.5rem">
    <Card accent="rust"><h3>Sketch</h3><p class="muted">手绘或线稿草图，检索结构相近的零件。</p></Card>
    <Card accent="teal"><h3>Text → 3D</h3><p class="muted">一句话描述形状特征，返回 top-K 三维模型。</p></Card>
    <Card accent="amber"><h3>Image → 3D</h3><p class="muted">拍一张现有零件，找数据库里最像的件。</p></Card>
  </div>

  <h2 class="section-title">为什么需要语义检索？</h2>
  <p>
    传统 CAD 库依赖<strong>文件名与元数据</strong>检索：零件叫什么、谁建的、什么时候建的。
    它无法回答工程师真正的问题——<em>"哪个件长得像这个、能替换它"</em>。形状语义没有被索引。
  </p>
  <div class="fig-grid cols-3">
    <Card><h3>替换选型</h3><p class="muted">手里有一个件，想在库里找功能/形状等价的替代品。</p></Card>
    <Card><h3>草图找件</h3><p class="muted">脑中有个形状，画几笔就想找到现成的 STEP 文件。</p></Card>
    <Card><h3>逆向检索</h3><p class="muted">拿到一张参考图，反查数据库里最接近的几何。</p></Card>
  </div>

  <h2 class="section-title">技术挑战</h2>
  <ul>
    <li><strong>多模态对齐</strong>：文本、草图、图像要投影到同一可比的潜空间。</li>
    <li><strong>大规模数据</strong>：ABC Dataset 有 1M STEP 文件，预处理本身就是一项工程。</li>
    <li><strong>实时检索</strong>：百万级向量库下，端到端延迟要压在亚秒级。</li>
  </ul>
</section>
```

- [ ] **Step 2: Commit**

```bash
git add presentations/cad-retriever/src/components/slides/Slide1Intro.astro
git commit -m "feat(deck): slide 1 — intro & problem statement"
```

---

### Task 8b: Slide 2 — Dataset Preprocessing Pipeline

**Files:**
- Create: `presentations/cad-retriever/src/components/slides/Slide2Dataset.astro`

**Interfaces:**
- Consumes: `Pill`, `Card`, `CodeBlock`, `StatBar` from `../ui/`. Renders `<section class="deck-section">`.
- The 30-view azimuth ring dots are positioned by a small inline `<script>` that places `.view-dot` elements at the 10 azimuth angles.

- [ ] **Step 1: Create `Slide2Dataset.astro`**

```astro
---
import Pill from "../ui/Pill.astro";
import Card from "../ui/Card.astro";
import CodeBlock from "../ui/CodeBlock.astro";
import StatBar from "../ui/StatBar.astro";
const renderStack = `STEP → Blender headless 加载 → 居中 + 归一化缩放
   → 30 相机位 (10 方位角 × 3 仰角) → EEVEE GPU 渲染
   → 224×224 JPEG q90 彩色图 × 30`;
const annoPrompt = `Describe this CAD part's geometry in one sentence.
Focus on shape, structure, and key features (holes, threads, flanges).
Example: a flat cylindrical disc with a central through-hole
and six evenly spaced mounting holes.`;
---
<section class="deck-section">
  <Pill label="Pipeline · ABC Dataset" />
  <h2 class="section-title">Dataset Preprocessing</h2>
  <p>
    数据来自 <strong>ABC Dataset</strong>（Koch et al., CVPR 2019）：
    约 <strong>1M STEP</strong> 文件、~500GB，解压建议预留 700GB。
    预处理把每个 CAD 模型变成可训练的三模态样本：多视角渲染图、草图、文本描述。
  </p>

  <div class="flow">
    <div class="flow-step"><div>Multi-view Rendering</div><div class="when">~60h</div></div>
    <div class="flow-arrow">→</div>
    <div class="flow-step"><div>Sketch Generation</div><div class="when">~144h</div></div>
    <div class="flow-arrow">→</div>
    <div class="flow-step"><div>Text Annotation</div><div class="when">~16h</div></div>
  </div>

  <h3>① Multi-view Rendering</h3>
  <p class="muted">Blender headless + EEVEE GPU，逐视角渲染。30-view = 10 方位角 × 3 仰角。</p>
  <div class="fig-grid cols-2">
    <div>
      <div class="view-ring" id="view-ring"><div class="center">10 方位角<br/>× 3 仰角</div></div>
      <div class="elev-legend">
        <span style="--d:var(--teal)">仰角 15°</span>
        <span style="color:var(--amber)">35°</span>
        <span style="color:var(--rust)">60°</span>
      </div>
    </div>
    <div>
      <CodeBlock code={renderStack} />
      <p class="muted">输出：224×224 JPEG q90，1M × 30 = <strong>30M</strong> 图像，~625GB。</p>
    </div>
  </div>

  <h3>② Sketch Generation</h3>
  <p class="muted">从 30-view 抽 6-view，提 lineart 作 ControlNet 条件，SDXL-Lightning 4-step 生成灰度草图。</p>
  <div class="fig-grid cols-3">
    <Card accent="teal"><h3>SDXL-Lightning</h3><p class="muted">HF ByteDance/SDXL-Lightning（4-step UNet）</p></Card>
    <Card accent="rust"><h3>ControlNet Lineart</h3><p class="muted">HF xinsir/controlnet-scribble-sdxl-1.0</p></Card>
    <Card accent="amber"><h3>Lineart 预处理</h3><p class="muted">controlnet_aux LineartDetector</p></Card>
  </div>
  <p class="muted">输出：1M × 6 = <strong>6M</strong> 灰度 JPEG，~40GB。</p>

  <h3>③ Text Annotation</h3>
  <p class="muted">Qwen3.6-27B（multi-image input，吃全部 30 视角）产出 shape-centric caption，风格参考 NURBGen partABC（~300K captions, arXiv 2511.06194）。27B fp16 ~54GB，需双卡。</p>
  <CodeBlock code={annoPrompt} />
  <p class="muted">输出：1M JSON，~1GB。</p>

  <h2 class="section-title">耗时对比（1× RTX 5090，标注阶段 2×）</h2>
  <StatBar label="Multi-view Rendering" value={60} max={144} unit="h" accent="teal" />
  <StatBar label="Sketch Generation" value={144} max={144} unit="h" accent="rust" />
  <StatBar label="Text Annotation" value={16} max={144} unit="h" accent="amber" />

  <script>
    // place 10 azimuth dots around the ring
    const ring = document.getElementById("view-ring");
    if (ring) {
      const R = 100, C = 110;
      for (let i = 0; i < 10; i++) {
        const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
        const dot = document.createElement("div");
        dot.className = "view-dot";
        dot.style.left = `${C + R * Math.cos(a)}px`;
        dot.style.top = `${C + R * Math.sin(a)}px`;
        ring.appendChild(dot);
      }
    }
  </script>
</section>
```

- [ ] **Step 2: Commit**

```bash
git add presentations/cad-retriever/src/components/slides/Slide2Dataset.astro
git commit -m "feat(deck): slide 2 — dataset preprocessing pipeline"
```

---

### Task 8c: Slide 3 — Quality Filtering Strategy

**Files:**
- Create: `presentations/cad-retriever/src/components/slides/Slide3Quality.astro`

**Interfaces:**
- Consumes: `Pill`, `CodeBlock` from `../ui/`. Uses `.data-table`, `.funnel`, `.pull-quote` from `figures.css`.

- [ ] **Step 1: Create `Slide3Quality.astro`**

```astro
---
import Pill from "../ui/Pill.astro";
import CodeBlock from "../ui/CodeBlock.astro";
const probeCode = `reader = STEPControl_Reader()
if reader.ReadFile(step_path) != 1:
    flag = "step_read_fail"
explorer = TopExp_Explorer(shape, TopAbs_FACE)   # no BRepMesh
n_faces = count(explorer)
if n_faces > 5000:  flag = "too_complex"
if n_faces < 3:     flag = "too_simple"`;
---
<section class="deck-section">
  <Pill label="Preprocessing · Quality Gate" />
  <h2 class="section-title">显式、廉价、可解释的质量门</h2>

  <p>
    上次执行渲染卡在 <strong>276K / 990K</strong>：剩余 STEP "太复杂渲染不动"，
    被迫把训练阈值从 900K 硬降到 340K。换句话说，
    <em>"能否在 30s 内 mesh 完"</em> 偷偷变成了筛选规则——一种不可控的隐式筛选。
  </p>
  <div class="pull-quote">
    把质量筛选从渲染 timeout 的副产物，提前到渲染之前：变成显式、廉价、可解释、可复现的一步。
  </div>
  <p class="muted">
    核心原则：在 mesh（BRepMesh，最贵且超时所在）之前，用便宜的拓扑探查预测哪些会爆炸，提前分流。
    筛选<strong>不删除文件</strong>，只往 manifest 写 <code>quality_flags</code> 列——随时可查询、复核、判断是否误杀。
  </p>

  <h3>四阶段筛选（按成本递增）</h3>
  <table class="data-table">
    <thead><tr><th>阶段</th><th>成本</th><th>检测项</th><th>Flag</th></tr></thead>
    <tbody>
      <tr><td>1 · 元数据级</td><td>零解析</td><td>file_size &gt; 50MB / ≈0；ABC <code>*_features.yml</code></td><td><code>oversized</code> / <code>corrupt</code></td></tr>
      <tr><td>2 · 拓扑探查</td><td>秒级，不 mesh</td><td>ReadFile≠1；n_faces&gt;5000 / &lt;3；n_solids==0；bbox 比&gt;1000:1</td><td><code>too_complex</code> / <code>too_simple</code> / <code>no_solid</code> / <code>degenerate</code></td></tr>
      <tr><td>3 · 图像级</td><td>廉价（可选）</td><td>前景像素&lt;1%；视角间方差极低</td><td><code>blank_render</code> / <code>low_variance</code></td></tr>
      <tr><td>4 · 语义去重</td><td>后期（CLIP）</td><td>余弦相似度近重复；多样性采样</td><td>dedup 标记</td></tr>
    </tbody>
  </table>

  <h3>拓扑探查：筛选主力</h3>
  <p class="muted">STEPControl_Reader + TopExp_Explorer，秒级遍历拓扑，<strong>完全不调 BRepMesh</strong>。</p>
  <CodeBlock code={probeCode} lang="python" />

  <h3>Manifest 新增列</h3>
  <table class="data-table">
    <thead><tr><th>列名</th><th>含义</th></tr></thead>
    <tbody>
      <tr><td><code>probe_n_faces</code></td><td>拓扑探查得到的面数</td></tr>
      <tr><td><code>probe_n_solids</code></td><td>实体个数（装配体判定）</td></tr>
      <tr><td><code>probe_bbox_ratio</code></td><td>包围盒长宽比（退化判定）</td></tr>
      <tr><td><code>file_size_mb</code></td><td>文件大小（几何爆炸预判）</td></tr>
      <tr><td><code>quality_flags</code></td><td>命中的筛选 flag 列表</td></tr>
    </tbody>
  </table>

  <div class="pull-quote">
    待拍板：检索面向<strong>零件级</strong>还是<strong>装配体级</strong>？这决定 <code style="color:var(--rust)">n_solids &gt; 1</code> 是噪声（筛掉）还是信号（慢速渲染队列特殊处理）。
  </div>

  <h3>筛选漏斗（最终数量待 probe 跑完定）</h3>
  <div class="funnel">
    <div class="funnel-row" style="width:100%">1,000K STEP 文件</div>
    <div class="funnel-row" style="width:88%">元数据筛后</div>
    <div class="funnel-row" style="width:72%">拓扑探查筛后</div>
    <div class="funnel-row" style="width:66%">图像级筛后</div>
    <div class="funnel-row illustrative" style="width:60%">render-eligible（示意值，非实测）</div>
  </div>
  <p class="muted">阈值看真实直方图定，而非拍脑袋的 340K。漏斗末端数字为示意，待 <code>probe.py</code> 首次跑完确定。</p>
</section>
```

- [ ] **Step 2: Commit**

```bash
git add presentations/cad-retriever/src/components/slides/Slide3Quality.astro
git commit -m "feat(deck): slide 3 — quality filtering strategy"
```

---

### Task 8d: Slide 4 — System Architecture

**Files:**
- Create: `presentations/cad-retriever/src/components/slides/Slide4Arch.astro`

**Interfaces:**
- Consumes: `Pill`, `Card`, `StatBar` from `../ui/`. Uses `.arch-layer`, `.flow`, `.data-table` from `figures.css`.
- All latency figures rendered as **targets** (per Global Constraints). The InfoNCE formula is rendered as plain text/HTML (no KaTeX dependency — keeps the deck dependency-free).

- [ ] **Step 1: Create `Slide4Arch.astro`**

```astro
---
import Pill from "../ui/Pill.astro";
import Card from "../ui/Card.astro";
import StatBar from "../ui/StatBar.astro";
---
<section class="deck-section">
  <Pill label="System · Architecture" />
  <h2 class="section-title">端到端多模态检索</h2>
  <p class="muted">以下为<strong>计划/目标设计</strong>（非实测）：对比学习把三模态编码进共享空间，FAISS 做向量检索，前端渲染 3D 结果。</p>

  <div>
    <div class="arch-layer"><span class="layer-name">Frontend</span> — Astro + three.js 3D viewer（OrbitControls，实时 thumbnail 渲染）</div>
    <div class="arch-sep">▲</div>
    <div class="arch-layer"><span class="layer-name">Embedding Model</span> — Contrastive Learning：InfoNCE loss + hard negative mining</div>
    <div class="arch-sep">▲</div>
    <div class="arch-layer"><span class="layer-name">Backend</span> — FAISS 向量库（IVF / HNSW 索引）</div>
    <div class="arch-sep">▲</div>
    <div class="arch-layer"><span class="layer-name">Data</span> — ABC 1M 预处理（renders + sketches + captions）</div>
  </div>

  <h3>Contrastive Learning</h3>
  <div class="fig-grid cols-2">
    <Card accent="teal">
      <h3>InfoNCE</h3>
      <p class="muted">把匹配的 (模态A, 模态B) 拉近、不匹配推远：</p>
      <p style="font-family:var(--font-serif);font-style:italic;color:var(--amber)">
        L = −log [ exp(sim(q,k⁺)/τ) / Σ exp(sim(q,kᵢ)/τ) ]
      </p>
    </Card>
    <Card accent="rust">
      <h3>Hard Negative Mining</h3>
      <p class="muted">挑选"看起来像但其实不同"的负样本进入分母，迫使模型学习细粒度几何差异，而非靠简单负样本偷懒。</p>
    </Card>
  </div>
  <div class="modality" style="margin-top:.5rem">
    <Card accent="teal"><h3>Text enc</h3></Card>
    <div class="arch-sep">→</div>
    <div class="modality-converge">Shared Latent Space</div>
    <div class="arch-sep">←</div>
    <Card accent="amber"><h3>Image / Sketch enc</h3></Card>
  </div>

  <h3>技术栈</h3>
  <div class="fig-grid cols-2">
    <Card><h3>Frontend</h3><p class="muted">Astro · three.js · OrbitControls · 客户端 thumbnail 渲染</p></Card>
    <Card><h3>Backend</h3><p class="muted">FAISS（IVF/HNSW）· embedding 维度待定 · 亚秒级检索目标</p></Card>
  </div>

  <h3>数据流</h3>
  <div class="flow">
    <div class="flow-step">User input</div><div class="flow-arrow">→</div>
    <div class="flow-step">Encode</div><div class="flow-arrow">→</div>
    <div class="flow-step">Query FAISS</div><div class="flow-arrow">→</div>
    <div class="flow-step">Top-K</div><div class="flow-arrow">→</div>
    <div class="flow-step">Render 3D + meta</div>
  </div>

  <h3>性能目标（design targets，非实测）</h3>
  <StatBar label="Embedding inference" value={50} max={500} unit="ms" accent="teal" />
  <StatBar label="FAISS retrieval" value={100} max={500} unit="ms" accent="amber" />
  <StatBar label="3D model loading" value={200} max={500} unit="ms" accent="rust" />
  <StatBar label="Total latency (target)" value={500} max={500} unit="ms" accent="teal" />
</section>
```

- [ ] **Step 2: Commit**

```bash
git add presentations/cad-retriever/src/components/slides/Slide4Arch.astro
git commit -m "feat(deck): slide 4 — system architecture"
```

---

### Task 8e: Slide 5 — Live Demo (embeds the web app)

**Files:**
- Create: `presentations/cad-retriever/src/components/slides/Slide5Demo.astro`

**Interfaces:**
- Consumes: `Pill` from `../ui/`; `SearchBar`, `ResultsGrid`, `ViewerModal` from `../webapp/`; imports `../../styles/webapp.css`.
- Wraps the app in `<div id="demo-slide">` so `webapp.css` `#demo-slide …` rules apply and deck nav can detect input focus.
- This is the only section that does NOT use the default `--wash` (keep the demo readable on a darker, calmer ground).

- [ ] **Step 1: Create `Slide5Demo.astro`**

```astro
---
import Pill from "../ui/Pill.astro";
import SearchBar from "../webapp/SearchBar.astro";
import ResultsGrid from "../webapp/ResultsGrid.astro";
import ViewerModal from "../webapp/ViewerModal.astro";
import "../../styles/webapp.css";
---
<section class="deck-section" style="--wash-a:rgba(13,110,120,.18);--wash-b:rgba(10,26,46,0)">
  <Pill label="Live Demo · Interactive" />
  <h2 class="section-title">实机展示</h2>
  <p class="muted">
    试试三种检索模式：在搜索框输入描述，或点击图标上传草图 / 参考图。
    点任意结果行打开 3D viewer（鼠标拖动旋转）。
    <span style="color:var(--amber)">演示数据为 5 个固定 demo 模型。</span>
  </p>

  <div id="demo-slide">
    <SearchBar />
    <ResultsGrid />
    <ViewerModal />
  </div>

  <p class="muted" style="margin-top:1.5rem">
    提示：在搜索框内打字时方向键不会翻页；3D viewer 打开时同样锁定翻页。关闭弹窗或点空白处即可恢复 ↑ ↓ 翻页。
  </p>
</section>
```

- [ ] **Step 2: Commit**

```bash
git add presentations/cad-retriever/src/components/slides/Slide5Demo.astro
git commit -m "feat(deck): slide 5 — live demo embedding the web app"
```

---

### Task 9: Assemble index page + full build verification

**Files:**
- Modify: `presentations/cad-retriever/src/pages/index.astro` (replace the Task 1 smoke page)
- Test: `presentations/cad-retriever/test/deck.test.mjs` (create)

**Interfaces:**
- Consumes: `Deck` layout + all five slide components.
- Produces: the final deck page. `npm run build` emits `dist/index.html` containing all 5 sections and the 5 embedded demo model cards.

- [ ] **Step 1: Replace `src/pages/index.astro`**

```astro
---
import Deck from "../layouts/Deck.astro";
import Slide1Intro from "../components/slides/Slide1Intro.astro";
import Slide2Dataset from "../components/slides/Slide2Dataset.astro";
import Slide3Quality from "../components/slides/Slide3Quality.astro";
import Slide4Arch from "../components/slides/Slide4Arch.astro";
import Slide5Demo from "../components/slides/Slide5Demo.astro";
---
<Deck title="CAD Retriever — Presentation">
  <Slide1Intro />
  <Slide2Dataset />
  <Slide3Quality />
  <Slide4Arch />
  <Slide5Demo />
</Deck>
```

- [ ] **Step 2: Write `test/deck.test.mjs`**

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../dist/index.html", import.meta.url), "utf-8");

test("deck has exactly 5 sections", () => {
  const matches = html.match(/class="[^"]*deck-section[^"]*"/g) ?? [];
  assert.equal(matches.length, 5);
});
test("demo slide embeds 5 model cards", () => {
  const matches = html.match(/class="[^"]*model-card[^"]*"/g) ?? [];
  assert.equal(matches.length, 5);
});
test("uses the cyberpunk palette, not the old green", () => {
  assert.ok(html.includes("#0D6E78") || html.includes("0D6E78"));
  assert.ok(!/#2a7\b/i.test(html));
});
```

- [ ] **Step 3: Build the deck**

Run (from `presentations/cad-retriever/`): `npm run build`
Expected: build succeeds; `dist/index.html` generated. Watch for: unresolved imports, bad `<script src>` paths (Astro errors at build if a referenced script doesn't exist).

- [ ] **Step 4: Run the deck tests**

Run: `node --test test/deck.test.mjs test/nav-core.test.mjs`
Expected: all PASS (5 sections, 5 model cards, palette present).

- [ ] **Step 5: Manual smoke (dev server)**

Run: `npm run dev` (or `astro dev --background` then `astro dev logs`). Open `http://localhost:4321`.
Verify by hand:
1. Arrow Down / PageDown / Space flips to next slide with a 600ms slide animation; progress shows `2 / 5` … `5 / 5`.
2. On a long slide (Slide 3), the mouse wheel scrolls content; only when scrolled to the bottom does one more wheel-down flip to the next slide.
3. Arrow Up / PageUp flips back; Home jumps to slide 1, End to slide 5.
4. On Slide 5: click the text input and type — arrow keys move the caret, do NOT flip slides. Click a result row — 3D modal opens full-viewport (not clipped), drag rotates; Escape or × closes; modalOpen flag cleared so keys flip again.
5. Thumbnails render in the results table; `score` is amber; row hover is teal-tinted.

- [ ] **Step 6: Commit**

```bash
git add presentations/cad-retriever/src/pages/index.astro presentations/cad-retriever/test/deck.test.mjs
git commit -m "feat(deck): assemble 5-slide index + build/card-count tests"
```

---

## Self-Review

**Spec coverage:**
- Navigation model (within-page scroll + flip + boundary auto-flip) → Task 3 (nav-core + deck-nav) + Task 4 (CSS) + Task 9 step 5 manual checks. ✓
- Visual system / palette / fonts / density → Task 4 (deck.css), Task 5 (primitives), Task 6 (figures). ✓
- Web app restyle (canonical in `web/`) → Task 2. ✓
- Demo embed native, scoped under `#demo-slide` → Task 7 + Task 8e. ✓
- CSS isolation → Task 7 (scoped webapp.css) + Task 4 (deck `deck-*` prefixes). ✓
- Modal not clipped + key suppression → Task 7 (z-index:100, body.dataset.modalOpen), Task 3 (shouldSuppressKeys), Task 9 step 5. ✓
- 5 slides with specified content → Tasks 8a–8e. ✓
- Honesty labels (targets / illustrative) → Task 8c funnel, Task 8d latency. ✓
- Build succeeds + node:test checks → Task 2, 3, 9. ✓
- Three dependency, Node engine → Global Constraints + Task 1. ✓

**Placeholder scan:** No TBD/TODO left in steps; the only "TBD"-like text is intentional in-slide copy (eligible count "待 probe 跑完定"), which the spec requires. ✓

**Type consistency:** `atEdge`/`nextIndex`/`shouldSuppressKeys` signatures match between Task 3 test and impl. `deck-nav.ts` reads `body.dataset.modalOpen`; `viewer.ts` (Task 7) writes it with `"1"`/`"0"`. Model shape consistent across `models.json`, `ModelCard`, `viewer.ts`. Script `src` paths fixed for the two-level-deeper webapp folder in Task 7. ✓

**Note on `node --test` + `.ts` imports:** Tasks 3/9 import `.ts` from `.mjs` tests, relying on Node ≥22.12 type-stripping (project engine enforces this). If the executing environment's Node cannot strip types at import, the fallback is to run these checks via `astro check` + the built-HTML tests only (deck.test.mjs reads `dist/`, needs no `.ts` import). The nav-core unit test is the one affected; keep it but note this fallback.

