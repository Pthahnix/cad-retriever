# CAD Retriever Demo Web App Implementation Plan (simplified, no Python)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **2026-06-22 simplification:** the Python/build123d CAD generator is dropped for this
> first build. No real STEP/GLB/PNG assets. `models.json` is hand-written; the three.js
> viewer renders **procedural primitive geometry** per `shape`; thumbnails are CSS
> placeholders; "Download STEP" is deferred. This supersedes the earlier 5-task plan.

**Goal:** Build a static web app that looks like a working cross-modal CAD search engine, with a three.js viewer showing procedurally-generated stand-in geometry for 5 hand-authored demo models.

**Architecture:** A static Astro site (no backend, no ML, no Python). A hand-written `models.json` holds 5 entries, each with a `shape` tag. Search is cosmetic — any query returns the same fixed list. Clicking a result opens a three.js modal that builds an approximate shape from primitives (cylinders/boxes) for that `shape`.

**Tech Stack:** Astro (static, TypeScript), three.js (vanilla, via `<script>` islands — no UI framework), Node's built-in test runner for the web check.

## Global Constraints

- **Static only** — no backend, no database, no ML, **no Python**. Everything baked at build time.
- **Search is hardcoded** — text / sketch / image inputs are all cosmetic; every query returns the same 5 models in the same order. Uploads accepted but ignored.
- **Exactly 5 demo models**, hand-authored in `models.json`. No external dataset, no generated files.
- **3D viewer = three.js**, building primitive geometry per `shape` (no GLB loading).
- **No UI framework** — three.js and search wired through Astro `<script>` tags (vanilla TS).
- `models.json` lives in `web/src/data/models.json` (build-time import).
- Node 24 / npm 11 confirmed present.

---

### Task 1: Scaffold the Astro site

**Files:**
- Create: `web/` (Astro minimal template, TypeScript strict)
- Create: `web/package.json`, `web/astro.config.mjs`, `web/tsconfig.json`, `web/src/pages/index.astro` (from template)
- Modify: `.gitignore` (ignore `web/node_modules/` and `web/dist/`)

**Interfaces:**
- Produces: a `web/` Astro project that runs `npm run build` and emits `web/dist/index.html`. Later tasks add components and scripts under `web/src/`.

- [ ] **Step 1: Scaffold Astro non-interactively**

Run from repo root (`G:\cad-retriever`):
```bash
npm create astro@latest web -- --template minimal --typescript strict --no-install --no-git --yes
```
Expected: creates `web/` with `package.json`, `astro.config.mjs`, `tsconfig.json`, `src/pages/index.astro`.

- [ ] **Step 2: Install dependencies + three.js**

```bash
cd web
npm install
npm install three
npm install -D @types/three
cd ..
```
Expected: `web/node_modules/` populated; `three` and `@types/three` in `web/package.json`.

- [ ] **Step 3: Ignore build artifacts**

Append to `.gitignore`:
```
# web app
web/node_modules/
web/dist/
```

- [ ] **Step 4: Verify the site builds**

```bash
cd web && npm run build && cd ..
```
Expected: build succeeds, `web/dist/index.html` exists.

- [ ] **Step 5: Commit**

```bash
git add web .gitignore
git commit -m "chore: scaffold static Astro site with three.js"
```

---

### Task 2: Hand-authored models.json + results grid

**Files:**
- Create: `web/src/data/models.json`
- Create: `web/src/components/ModelCard.astro`
- Create: `web/src/components/ResultsGrid.astro`
- Create: `web/src/styles/global.css`
- Modify: `web/src/pages/index.astro`
- Create: `web/test/grid.test.mjs`

**Interfaces:**
- Produces: `models.json` — array of 5 objects:
  ```
  { "id": str, "caption": str, "shape": "disc"|"bracket"|"nut"|"shaft"|"plate",
    "score": float, "probe": { "n_faces": int, "n_solids": int,
    "bbox_ratio": float, "quality_flags": list[str] } }
  ```
  Each card carries `class="model-card"` and `data-model-id={id}`. The viewer (Task 4) keys off `data-model-id` → looks up `shape` in the imported JSON.

- [ ] **Step 1: Write models.json**

Create `web/src/data/models.json`:
```json
[
  {
    "id": "demo/0001",
    "caption": "a flat cylindrical disc with a central through-hole and six evenly spaced mounting holes",
    "shape": "disc",
    "score": 0.94,
    "probe": { "n_faces": 16, "n_solids": 1, "bbox_ratio": 10.0, "quality_flags": [] }
  },
  {
    "id": "demo/0002",
    "caption": "an L-shaped mounting bracket with two perpendicular flat arms",
    "shape": "bracket",
    "score": 0.89,
    "probe": { "n_faces": 12, "n_solids": 1, "bbox_ratio": 6.3, "quality_flags": [] }
  },
  {
    "id": "demo/0003",
    "caption": "a hexagonal nut with a central circular bore",
    "shape": "nut",
    "score": 0.85,
    "probe": { "n_faces": 9, "n_solids": 1, "bbox_ratio": 3.0, "quality_flags": [] }
  },
  {
    "id": "demo/0004",
    "caption": "a stepped cylindrical shaft with two coaxial diameters",
    "shape": "shaft",
    "score": 0.81,
    "probe": { "n_faces": 6, "n_solids": 1, "bbox_ratio": 4.7, "quality_flags": [] }
  },
  {
    "id": "demo/0005",
    "caption": "a rectangular base plate reinforced with three parallel ribs",
    "shape": "plate",
    "score": 0.76,
    "probe": { "n_faces": 30, "n_solids": 1, "bbox_ratio": 13.3, "quality_flags": [] }
  }
]
```

- [ ] **Step 2: Write the failing test**

Create `web/test/grid.test.mjs`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("built page renders exactly 5 model cards", () => {
  const html = readFileSync(new URL("../dist/index.html", import.meta.url), "utf-8");
  const matches = html.match(/class="[^"]*model-card[^"]*"/g) ?? [];
  assert.equal(matches.length, 5);
});
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: FAIL — minimal `index.astro` renders 0 cards (assert 0 !== 5).

- [ ] **Step 4: Write the card component**

Create `web/src/components/ModelCard.astro`:
```astro
---
interface Props {
  id: string;
  caption: string;
  shape: string;
  score: number;
  probe: { n_faces: number; n_solids: number; bbox_ratio: number; quality_flags: string[] };
}
const { id, caption, shape, score, probe } = Astro.props;
---
<button class="model-card" data-model-id={id}>
  <div class={`thumb thumb-${shape}`} aria-hidden="true"></div>
  <p class="caption">{caption}</p>
  <div class="meta">
    <span class="score">{score.toFixed(2)}</span>
    <span class="chip">{probe.n_faces} faces</span>
    <span class="chip">{probe.n_solids} solid</span>
    {probe.quality_flags.map((f) => <span class="chip flag">{f}</span>)}
  </div>
</button>
```

- [ ] **Step 5: Write the grid component**

Create `web/src/components/ResultsGrid.astro`:
```astro
---
import ModelCard from "./ModelCard.astro";
import models from "../data/models.json";
---
<section class="results-grid">
  {models.map((m) => <ModelCard {...m} />)}
</section>
```

- [ ] **Step 6: Write styles + wire the page**

Create `web/src/styles/global.css`:
```css
:root { font-family: system-ui, sans-serif; color: #1a2530; background: #f4f6f8; }
body { margin: 0; padding: 2rem; }
h1 { font-size: 1.4rem; }
.results-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; transition: opacity 0.2s; }
.model-card { text-align: left; background: #fff; border: 1px solid #dde3e8; border-radius: 8px; padding: 0.75rem; cursor: pointer; font: inherit; }
.thumb { width: 100%; aspect-ratio: 1; border-radius: 6px; background: linear-gradient(135deg, #c3d2de, #7c9cb5); display: grid; place-items: center; }
.thumb::after { content: attr(class); }  /* placeholder; visual only */
.thumb-disc { background: radial-gradient(circle, #7c9cb5 40%, #c3d2de 42%); }
.thumb-bracket { background: linear-gradient(135deg, #b5c7d4, #6f93ac); }
.thumb-nut { background: conic-gradient(#7c9cb5 0 16%, #c3d2de 0 33%, #7c9cb5 0 50%, #c3d2de 0 66%, #7c9cb5 0 83%, #c3d2de 0 100%); }
.thumb-shaft { background: linear-gradient(90deg, #c3d2de 30%, #7c9cb5 30%); }
.thumb-plate { background: repeating-linear-gradient(90deg, #7c9cb5 0 8px, #c3d2de 8px 20px); }
.thumb::after { content: ""; }  /* hide debug text */
.caption { font-size: 0.85rem; margin: 0.5rem 0; }
.meta { display: flex; flex-wrap: wrap; gap: 0.25rem; align-items: center; }
.score { font-weight: 600; color: #2a7; }
.chip { font-size: 0.7rem; background: #eef2f5; border-radius: 4px; padding: 0.1rem 0.4rem; }
.chip.flag { background: #fde2e2; color: #a33; }
```

Replace `web/src/pages/index.astro`:
```astro
---
import "../styles/global.css";
import ResultsGrid from "../components/ResultsGrid.astro";
---
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>CAD Retriever — Demo</title>
  </head>
  <body>
    <h1>CAD Retriever</h1>
    <ResultsGrid />
  </body>
</html>
```

- [ ] **Step 7: Run the test to verify it passes**

```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: PASS — 5 `model-card` matches.

- [ ] **Step 8: Commit**

```bash
git add web/src web/test
git commit -m "feat: hand-authored models.json + results grid (5 cards, CSS thumbs)"
```

---

### Task 3: Search bar (cosmetic) + suggested queries

**Files:**
- Create: `web/src/components/SearchBar.astro`
- Create: `web/src/scripts/search.ts`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/styles/global.css`

**Interfaces:**
- Consumes: nothing (purely client-side cosmetic).
- Produces: a search UI above the grid. Submitting any query (any mode) re-shows the same grid after a brief fake "Searching…" shimmer. Uploads accepted and ignored.

- [ ] **Step 1: Write the search bar component**

Create `web/src/components/SearchBar.astro`:
```astro
---
const examples = [
  "flat disc with mounting holes",
  "L-shaped bracket",
  "hex nut",
  "stepped shaft",
];
---
<section class="search">
  <div class="tabs" role="tablist">
    <button class="tab active" data-mode="text">Text</button>
    <button class="tab" data-mode="sketch">Sketch</button>
    <button class="tab" data-mode="image">Image</button>
  </div>
  <div class="input-row">
    <input id="text-input" type="text" placeholder="Describe a CAD part…" />
    <input id="file-input" type="file" accept="image/*" hidden />
    <button id="search-btn">Search</button>
  </div>
  <div class="examples">
    {examples.map((e) => <button class="example" data-q={e}>{e}</button>)}
  </div>
  <p id="status" class="status" hidden>Searching…</p>
</section>
<script src="../scripts/search.ts"></script>
```

- [ ] **Step 2: Write the cosmetic search script**

Create `web/src/scripts/search.ts`:
```ts
// Search is intentionally cosmetic: any query shows the same fixed results.
const tabs = document.querySelectorAll<HTMLButtonElement>(".tab");
const textInput = document.querySelector<HTMLInputElement>("#text-input")!;
const fileInput = document.querySelector<HTMLInputElement>("#file-input")!;
const searchBtn = document.querySelector<HTMLButtonElement>("#search-btn")!;
const status = document.querySelector<HTMLParagraphElement>("#status")!;
const grid = document.querySelector<HTMLElement>(".results-grid")!;
const examples = document.querySelectorAll<HTMLButtonElement>(".example");

let mode: "text" | "sketch" | "image" = "text";

function setMode(next: "text" | "sketch" | "image") {
  mode = next;
  tabs.forEach((t) => t.classList.toggle("active", t.dataset.mode === next));
  const fileMode = next !== "text";
  textInput.hidden = fileMode;
  fileInput.hidden = !fileMode;
}

function runSearch() {
  // ponytail: hardcoded retrieval — fake latency, then reveal the same grid
  status.hidden = false;
  grid.style.opacity = "0.3";
  setTimeout(() => {
    status.hidden = true;
    grid.style.opacity = "1";
  }, 450);
}

tabs.forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode as typeof mode)));
searchBtn.addEventListener("click", runSearch);
textInput.addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
fileInput.addEventListener("change", runSearch);
examples.forEach((b) =>
  b.addEventListener("click", () => { setMode("text"); textInput.value = b.dataset.q ?? ""; runSearch(); })
);
```

- [ ] **Step 3: Add search styles**

Append to `web/src/styles/global.css`:
```css
.search { margin-bottom: 1.5rem; }
.tabs { display: flex; gap: 0.25rem; margin-bottom: 0.5rem; }
.tab { font: inherit; padding: 0.3rem 0.8rem; border: 1px solid #dde3e8; background: #fff; border-radius: 6px 6px 0 0; cursor: pointer; }
.tab.active { background: #1a2530; color: #fff; }
.input-row { display: flex; gap: 0.5rem; }
.input-row input[type="text"] { flex: 1; padding: 0.5rem; border: 1px solid #c7d0d8; border-radius: 6px; font: inherit; }
#search-btn { padding: 0.5rem 1.2rem; border: none; background: #2a7; color: #fff; border-radius: 6px; cursor: pointer; font: inherit; }
.examples { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.6rem; }
.example { font-size: 0.75rem; background: #eef2f5; border: 1px solid #dde3e8; border-radius: 999px; padding: 0.2rem 0.7rem; cursor: pointer; }
.status { color: #678; font-size: 0.85rem; }
```

- [ ] **Step 4: Mount the search bar**

In `web/src/pages/index.astro`, add the import and place above the grid:
```astro
---
import "../styles/global.css";
import SearchBar from "../components/SearchBar.astro";
import ResultsGrid from "../components/ResultsGrid.astro";
---
```
In the body:
```astro
    <h1>CAD Retriever</h1>
    <SearchBar />
    <ResultsGrid />
```

- [ ] **Step 5: Verify build + grid test still passes**

```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: build succeeds, grid test PASSES. Manually (`npm run dev`): tabs switch, examples fill the box, Search shows the shimmer.

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat: cosmetic text/sketch/image search bar with example queries"
```

---

### Task 4: three.js modal viewer with procedural geometry

**Files:**
- Create: `web/src/components/ViewerModal.astro`
- Create: `web/src/scripts/shapes.ts`
- Create: `web/src/scripts/viewer.ts`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/styles/global.css`

**Interfaces:**
- Consumes: `model-card` buttons with `data-model-id` (Task 2); `models.json` for `shape`/`caption`/`probe`.
- Produces: clicking a card opens a modal with a live three.js view of a primitive approximation of that `shape`, plus full caption + metadata. Esc / click-outside closes.

- [ ] **Step 1: Write the shape builder**

Create `web/src/scripts/shapes.ts`:
```ts
import * as THREE from "three";

// Build an approximate THREE.Group from primitives for each demo shape.
// ponytail: stand-in geometry, not real CAD — swap for GLB loading when real models exist.
const MAT = new THREE.MeshStandardMaterial({ color: 0x7c9cb5, metalness: 0.2, roughness: 0.6 });

function disc(): THREE.Group {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(40, 40, 8, 48), MAT);
  g.add(body);
  // visual nod to the bolt holes: 6 thin cylinders around the rim
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const hole = new THREE.Mesh(new THREE.CylinderGeometry(4, 4, 9, 16),
      new THREE.MeshStandardMaterial({ color: 0x33485a }));
    hole.position.set(Math.cos(a) * 28, 0, Math.sin(a) * 28);
    g.add(hole);
  }
  return g;
}

function bracket(): THREE.Group {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(50, 8, 40), MAT);
  base.position.set(25, 4, 0);
  const wall = new THREE.Mesh(new THREE.BoxGeometry(8, 50, 40), MAT);
  wall.position.set(4, 25, 0);
  g.add(base, wall);
  return g;
}

function nut(): THREE.Group {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(15, 15, 10, 6), MAT);
  const bore = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, 11, 32),
    new THREE.MeshStandardMaterial({ color: 0x33485a }));
  g.add(body, bore);
  return g;
}

function shaft(): THREE.Group {
  const g = new THREE.Group();
  const lo = new THREE.Mesh(new THREE.CylinderGeometry(15, 15, 40, 32), MAT);
  lo.position.y = 20;
  const hi = new THREE.Mesh(new THREE.CylinderGeometry(9, 9, 30, 32), MAT);
  hi.position.y = 55;
  g.add(lo, hi);
  return g;
}

function plate(): THREE.Group {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(80, 6, 50), MAT);
  g.add(base);
  for (let i = -1; i <= 1; i++) {
    const rib = new THREE.Mesh(new THREE.BoxGeometry(4, 10, 40), MAT);
    rib.position.set(i * 20, 8, 0);
    g.add(rib);
  }
  return g;
}

const BUILDERS: Record<string, () => THREE.Group> = { disc, bracket, nut, shaft, plate };

export function buildShape(shape: string): THREE.Group {
  return (BUILDERS[shape] ?? disc)();
}
```

- [ ] **Step 2: Write the viewer modal component**

Create `web/src/components/ViewerModal.astro`:
```astro
<div id="viewer-modal" class="modal" hidden>
  <div class="modal-backdrop" data-close></div>
  <div class="modal-body">
    <button class="modal-close" data-close aria-label="Close">×</button>
    <div id="viewer-canvas" class="viewer-canvas"></div>
    <p id="viewer-caption" class="viewer-caption"></p>
    <div id="viewer-meta" class="viewer-meta"></div>
  </div>
</div>
<script src="../scripts/viewer.ts"></script>
```

- [ ] **Step 3: Write the three.js viewer script**

Create `web/src/scripts/viewer.ts`:
```ts
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import models from "../data/models.json";
import { buildShape } from "./shapes";

type Model = (typeof models)[number];
const byId = new Map<string, Model>(models.map((m) => [m.id, m]));

const modal = document.querySelector<HTMLElement>("#viewer-modal")!;
const canvasHost = document.querySelector<HTMLElement>("#viewer-canvas")!;
const captionEl = document.querySelector<HTMLElement>("#viewer-caption")!;
const metaEl = document.querySelector<HTMLElement>("#viewer-meta")!;

let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let frame = 0;

function teardown() {
  if (frame) cancelAnimationFrame(frame);
  controls?.dispose();
  renderer?.dispose();
  renderer = null;
  canvasHost.innerHTML = "";
}

function open(model: Model) {
  captionEl.textContent = model.caption;
  metaEl.innerHTML =
    `<span>${model.probe.n_faces} faces</span>` +
    `<span>${model.probe.n_solids} solid</span>` +
    `<span>ratio ${model.probe.bbox_ratio}</span>`;
  modal.hidden = false;

  const w = canvasHost.clientWidth || 480;
  const h = 360;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf4f6f8);
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 5000);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(w, h);
  canvasHost.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
  const dir = new THREE.DirectionalLight(0xffffff, 1.0);
  dir.position.set(1, 1, 1);
  scene.add(dir);

  controls = new OrbitControls(camera, renderer.domElement);

  const obj = buildShape(model.shape);
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  obj.position.sub(center);
  const radius = Math.max(size.x, size.y, size.z) || 1;
  camera.position.set(radius * 1.6, radius * 1.2, radius * 1.8);
  controls.target.set(0, 0, 0);
  controls.update();
  scene.add(obj);

  const loop = () => {
    frame = requestAnimationFrame(loop);
    controls?.update();
    renderer?.render(scene, camera);
  };
  loop();
}

function close() {
  modal.hidden = true;
  teardown();
}

document.querySelectorAll<HTMLElement>(".model-card").forEach((card) => {
  card.addEventListener("click", () => {
    const m = byId.get(card.dataset.modelId ?? "");
    if (m) open(m);
  });
});
modal.querySelectorAll<HTMLElement>("[data-close]").forEach((el) =>
  el.addEventListener("click", close)
);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !modal.hidden) close(); });
```

- [ ] **Step 4: Add modal styles**

Append to `web/src/styles/global.css`:
```css
.modal { position: fixed; inset: 0; display: grid; place-items: center; z-index: 10; }
.modal[hidden] { display: none; }
.modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.5); }
.modal-body { position: relative; background: #fff; border-radius: 10px; padding: 1.25rem; max-width: 560px; width: 90%; }
.modal-close { position: absolute; top: 0.5rem; right: 0.75rem; border: none; background: none; font-size: 1.5rem; cursor: pointer; }
.viewer-canvas { width: 100%; min-height: 360px; background: #f4f6f8; border-radius: 6px; }
.viewer-caption { margin: 0.75rem 0 0.5rem; font-size: 0.95rem; }
.viewer-meta { display: flex; gap: 0.5rem; font-size: 0.75rem; color: #567; }
.viewer-meta span { background: #eef2f5; border-radius: 4px; padding: 0.1rem 0.5rem; }
```

- [ ] **Step 5: Mount the modal**

In `web/src/pages/index.astro` add the import and place `<ViewerModal />` just before `</body>`:
```astro
---
import "../styles/global.css";
import SearchBar from "../components/SearchBar.astro";
import ResultsGrid from "../components/ResultsGrid.astro";
import ViewerModal from "../components/ViewerModal.astro";
---
```
```astro
    <ViewerModal />
```

- [ ] **Step 6: Verify build + grid test + manual viewer check**

```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: build succeeds, grid test PASSES. Then `cd web && npm run dev`: click each card → modal opens with a rotatable primitive model matching the shape; Esc / click-outside closes.

- [ ] **Step 7: Commit**

```bash
git add web/src
git commit -m "feat: three.js modal viewer with procedural stand-in geometry"
```

---

## Self-Review

**Spec coverage (per simplification amendment):**
- Static Astro site, no backend/ML/Python → Task 1, Global Constraints. ✓
- Text/sketch/image inputs, cosmetic, uploads ignored → Task 3. ✓
- Hardcoded search returns same fixed list → Task 3 (`runSearch` reveals static grid). ✓
- 5 hand-authored models, no generated files → Task 2 `models.json`. ✓
- Results grid: CSS thumb, caption, score, probe chips → Task 2. ✓
- Modal three.js viewer with procedural geometry per shape → Task 4 (`shapes.ts` + `viewer.ts`). ✓
- Download STEP deferred → omitted intentionally, noted in amendment. ✓
- Testing: `astro build` + one grid component test → Tasks 2-4 build runs, Task 2 `grid.test.mjs`. ✓

**Placeholder scan:** No TBD/TODO; all code blocks complete. The `.thumb::after` debug line is immediately overridden to `content: ""` in the same stylesheet (intentional, keeps the shape-class swatches clean). ✓

**Type consistency:** `model-card` + `data-model-id` defined Task 2, consumed Task 4. `shape` enum values (`disc`/`bracket`/`nut`/`shaft`/`plate`) match between `models.json` (Task 2) and `BUILDERS` keys (Task 4). `models.json` fields consistent across Tasks 2/4 (`id`, `caption`, `shape`, `score`, `probe.{n_faces,n_solids,bbox_ratio,quality_flags}`). `buildShape` exported in `shapes.ts`, imported in `viewer.ts`. ✓
