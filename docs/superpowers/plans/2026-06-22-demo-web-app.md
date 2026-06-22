# CAD Retriever Demo Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static web app that demonstrates cross-modal CAD retrieval over 5 self-generated CAD models, with a three.js 3D viewer and a hardcoded search.

**Architecture:** A static Astro site (no backend, no ML). A one-shot Python generator (build123d) authors 5 CAD parts and exports the assets (`.step` / `.glb` / `.png` + `models.json`) the site consumes. Search is cosmetic — any query returns the same fixed ranked list. The only genuinely interactive piece is a three.js modal viewer.

**Tech Stack:** Astro (static, TypeScript), three.js (vanilla, via `<script>` islands — no UI framework), Python + build123d + trimesh + matplotlib (generator), Node's built-in test runner for the web check.

## Global Constraints

- **Static only** — no backend, no database, no ML inference. Everything baked at build time.
- **Search is hardcoded** — text / sketch / image inputs are all cosmetic; every query returns the same 5 models in the same fixed order. Uploads are accepted but ignored.
- **Exactly 5 demo models**, self-generated. No external dataset.
- **3D viewer = three.js + GLTFLoader + OrbitControls**, in a modal.
- **Generator = build123d**, run manually, separate from the site build, no dependency on the `cad_pipeline` package.
- **Asset split**: binary assets (`.glb` / `.step` / `.png`) live in `web/public/models/`; `models.json` lives in `web/src/data/models.json` (build-time import).
- **No UI framework** — three.js and search wired through Astro `<script>` tags (vanilla TS).
- Node 24 / npm 11 confirmed present. build123d is NOT yet installed.

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

Run:
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

### Task 2: Generator — 5 CAD parts + asset export + self-check

**Files:**
- Create: `demo-assets/generate.py`
- Create: `demo-assets/requirements.txt`
- Output (generated, committed): `web/public/models/000{1..5}.{step,glb,png}`, `web/src/data/models.json`

**Interfaces:**
- Produces: `web/src/data/models.json` — a JSON array of 5 objects, each:
  ```
  { "id": str, "caption": str, "glb": str, "step": str, "thumb": str,
    "score": float, "probe": { "n_faces": int, "n_solids": int,
    "bbox_ratio": float, "quality_flags": list[str] } }
  ```
  `glb`/`step`/`thumb` are site-absolute URLs (e.g. `/models/0001.glb`). Consumed by Tasks 3 and 5.

- [ ] **Step 1: Declare generator dependencies**

Create `demo-assets/requirements.txt`:
```
build123d
trimesh
matplotlib
```

Install:
```bash
python -m pip install -r demo-assets/requirements.txt
```
Expected: build123d, trimesh, matplotlib installed (build123d pulls in OCP/OpenCASCADE).

- [ ] **Step 2: Write the generator**

Create `demo-assets/generate.py`:
```python
"""Generate 5 demo CAD parts and export STEP + GLB + PNG + models.json.

Run manually:  python demo-assets/generate.py
Not part of the site build. Writes binaries to web/public/models/ and the
metadata index to web/src/data/models.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless, no OpenGL (reliable on Windows)
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import trimesh

from build123d import (
    Align, Axis, BuildLine, BuildPart, BuildSketch, Box, Cylinder,
    GridLocations, Hole, Locations, Mode, Plane, PolarLocations, Polyline,
    Rectangle, RegularPolygon, export_step, export_stl, extrude, make_face,
)

ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / "web" / "public" / "models"
DATA_DIR = ROOT / "web" / "src" / "data"


# --- 5 visually distinct parts ------------------------------------------

def flanged_disc():
    with BuildPart() as p:
        Cylinder(radius=40, height=8)
        Hole(radius=10)
        with PolarLocations(28, 6):
            Hole(radius=4)
    return p.part


def l_bracket():
    with BuildPart() as p:
        with BuildSketch(Plane.XZ):
            with BuildLine():
                Polyline(
                    (0, 0), (50, 0), (50, 8), (8, 8), (8, 50), (0, 50),
                    close=True,
                )
            make_face()
        extrude(amount=40)
    return p.part


def hex_nut():
    with BuildPart() as p:
        with BuildSketch():
            RegularPolygon(radius=15, side_count=6)
        extrude(amount=10)
        Hole(radius=8)
    return p.part


def stepped_shaft():
    with BuildPart() as p:
        Cylinder(radius=15, height=40,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((0, 0, 40)):
            Cylinder(radius=9, height=30,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def ribbed_plate():
    with BuildPart() as p:
        Box(80, 50, 6)
        top = p.faces().sort_by(Axis.Z)[-1]
        with BuildSketch(top):
            with GridLocations(20, 0, 3, 1):
                Rectangle(4, 40)
        extrude(amount=10)
    return p.part


# id, builder, caption, score, fake probe metadata
PARTS = [
    ("0001", flanged_disc,
     "a flat cylindrical disc with a central through-hole and six evenly spaced mounting holes",
     0.94, {"n_faces": 16, "n_solids": 1, "bbox_ratio": 10.0, "quality_flags": []}),
    ("0002", l_bracket,
     "an L-shaped mounting bracket with two perpendicular flat arms",
     0.89, {"n_faces": 12, "n_solids": 1, "bbox_ratio": 6.3, "quality_flags": []}),
    ("0003", hex_nut,
     "a hexagonal nut with a central circular bore",
     0.85, {"n_faces": 9, "n_solids": 1, "bbox_ratio": 3.0, "quality_flags": []}),
    ("0004", stepped_shaft,
     "a stepped cylindrical shaft with two coaxial diameters",
     0.81, {"n_faces": 6, "n_solids": 1, "bbox_ratio": 4.7, "quality_flags": []}),
    ("0005", ribbed_plate,
     "a rectangular base plate reinforced with three parallel ribs",
     0.76, {"n_faces": 30, "n_solids": 1, "bbox_ratio": 13.3, "quality_flags": []}),
]


def render_png(stl_path: Path, png_path: Path) -> None:
    mesh = trimesh.load(stl_path)
    fig = plt.figure(figsize=(3, 3))
    ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(
        Poly3DCollection(mesh.triangles, facecolor="#7c9cb5",
                         edgecolor="#33485a", linewidths=0.1)
    )
    b = mesh.bounds
    ax.set_xlim(b[0][0], b[1][0])
    ax.set_ylim(b[0][1], b[1][1])
    ax.set_zlim(b[0][2], b[1][2])
    ax.set_box_aspect((b[1] - b[0]))
    ax.set_axis_off()
    ax.view_init(elev=25, azim=45)
    fig.savefig(png_path, dpi=80, bbox_inches="tight", transparent=True)
    plt.close(fig)


def main() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    for pid, builder, caption, score, probe in PARTS:
        part = builder()
        step_path = BIN_DIR / f"{pid}.step"
        stl_path = BIN_DIR / f"{pid}.stl"
        glb_path = BIN_DIR / f"{pid}.glb"
        png_path = BIN_DIR / f"{pid}.png"

        export_step(part, str(step_path))
        export_stl(part, str(stl_path))
        trimesh.load(stl_path).export(glb_path)
        render_png(stl_path, png_path)
        stl_path.unlink()  # STL was only an intermediate

        index.append({
            "id": f"demo/{pid}",
            "caption": caption,
            "glb": f"/models/{pid}.glb",
            "step": f"/models/{pid}.step",
            "thumb": f"/models/{pid}.png",
            "score": score,
            "probe": probe,
        })

    (DATA_DIR / "models.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    _self_check(index)
    print(f"Generated {len(index)} models -> {BIN_DIR} and {DATA_DIR/'models.json'}")


def _self_check(index: list[dict]) -> None:
    assert len(index) == 5, f"expected 5 models, got {len(index)}"
    for entry in index:
        pid = entry["id"].split("/")[-1]
        for ext in ("step", "glb", "png"):
            f = BIN_DIR / f"{pid}.{ext}"
            assert f.exists() and f.stat().st_size > 0, f"missing/empty {f}"
        for key in ("id", "caption", "glb", "step", "thumb", "score", "probe"):
            assert key in entry, f"{pid} missing field {key}"
    print("self-check OK")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the generator and verify the self-check passes**

Run:
```bash
python demo-assets/generate.py
```
Expected: ends with `self-check OK` and `Generated 5 models ...`. If a build123d call errors (API drift), fix that part function and re-run — the self-check is your gate. `web/public/models/` now holds 15 files (5 each of step/glb/png); `web/src/data/models.json` has 5 entries.

- [ ] **Step 4: Commit**

```bash
git add demo-assets web/public/models web/src/data/models.json
git commit -m "feat: generator authors 5 demo CAD parts (STEP+GLB+PNG+models.json)"
```

---

### Task 3: Results grid renders the 5 models

**Files:**
- Create: `web/src/components/ModelCard.astro`
- Create: `web/src/components/ResultsGrid.astro`
- Modify: `web/src/pages/index.astro`
- Create: `web/src/styles/global.css`
- Create: `web/test/grid.test.mjs`

**Interfaces:**
- Consumes: `web/src/data/models.json` (from Task 2).
- Produces: each card carries `class="model-card"` and a `data-model-id` attribute equal to the model `id`. The viewer modal (Task 5) keys off these.

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: FAIL — the minimal `index.astro` renders 0 cards (assert 0 !== 5), or build has no cards yet.

- [ ] **Step 3: Write the card component**

Create `web/src/components/ModelCard.astro`:
```astro
---
interface Props {
  id: string;
  caption: string;
  thumb: string;
  score: number;
  probe: { n_faces: number; n_solids: number; bbox_ratio: number; quality_flags: string[] };
}
const { id, caption, thumb, score, probe } = Astro.props;
---
<button class="model-card" data-model-id={id}>
  <img src={thumb} alt={caption} width="160" height="160" loading="lazy" />
  <p class="caption">{caption}</p>
  <div class="meta">
    <span class="score">{score.toFixed(2)}</span>
    <span class="chip">{probe.n_faces} faces</span>
    <span class="chip">{probe.n_solids} solid</span>
    {probe.quality_flags.map((f) => <span class="chip flag">{f}</span>)}
  </div>
</button>
```

- [ ] **Step 4: Write the grid component**

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

- [ ] **Step 5: Wire the page + minimal styles**

Create `web/src/styles/global.css`:
```css
:root { font-family: system-ui, sans-serif; color: #1a2530; background: #f4f6f8; }
body { margin: 0; padding: 2rem; }
h1 { font-size: 1.4rem; }
.results-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; }
.model-card { text-align: left; background: #fff; border: 1px solid #dde3e8; border-radius: 8px; padding: 0.75rem; cursor: pointer; font: inherit; }
.model-card img { width: 100%; height: auto; display: block; }
.caption { font-size: 0.85rem; margin: 0.5rem 0; }
.meta { display: flex; flex-wrap: wrap; gap: 0.25rem; align-items: center; }
.score { font-weight: 600; color: #2a7; }
.chip { font-size: 0.7rem; background: #eef2f5; border-radius: 4px; padding: 0.1rem 0.4rem; }
.chip.flag { background: #fde2e2; color: #a33; }
```

Replace `web/src/pages/index.astro` with:
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

- [ ] **Step 6: Run the test to verify it passes**

Run:
```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: PASS — 5 `model-card` matches.

- [ ] **Step 7: Commit**

```bash
git add web/src web/test
git commit -m "feat: results grid renders 5 demo models from models.json"
```

---

### Task 4: Search bar (cosmetic) + suggested queries

**Files:**
- Create: `web/src/components/SearchBar.astro`
- Create: `web/src/scripts/search.ts`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/styles/global.css`

**Interfaces:**
- Consumes: nothing (purely client-side cosmetic).
- Produces: a search UI above the grid. Submitting any query (any mode) re-shows the same grid after a brief fake "Searching…" shimmer. Uploads are accepted and ignored.

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
  // text mode types; sketch/image upload a file (contents ignored)
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
.results-grid { transition: opacity 0.2s; }
```

- [ ] **Step 4: Mount the search bar on the page**

In `web/src/pages/index.astro`, add the import and place it above the grid:
```astro
---
import "../styles/global.css";
import SearchBar from "../components/SearchBar.astro";
import ResultsGrid from "../components/ResultsGrid.astro";
---
```
and in the body, before `<ResultsGrid />`:
```astro
    <h1>CAD Retriever</h1>
    <SearchBar />
    <ResultsGrid />
```

- [ ] **Step 5: Verify build + grid test still passes**

Run:
```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: build succeeds, grid test still PASSES (5 cards). Manually: `npm run dev`, confirm tabs switch, examples fill the box, Search shows the shimmer.

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat: cosmetic text/sketch/image search bar with example queries"
```

---

### Task 5: three.js modal viewer + Download STEP

**Files:**
- Create: `web/src/components/ViewerModal.astro`
- Create: `web/src/scripts/viewer.ts`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/styles/global.css`

**Interfaces:**
- Consumes: `model-card` buttons with `data-model-id` (Task 3); `models.json` for per-model `glb`/`step`/`caption`/`probe`.
- Produces: clicking a card opens a modal with a live three.js view of that model's GLB, full caption + metadata, and a Download STEP link. Esc / click-outside closes.

- [ ] **Step 1: Write the modal component**

Create `web/src/components/ViewerModal.astro`:
```astro
<div id="viewer-modal" class="modal" hidden>
  <div class="modal-backdrop" data-close></div>
  <div class="modal-body">
    <button class="modal-close" data-close aria-label="Close">×</button>
    <div id="viewer-canvas" class="viewer-canvas"></div>
    <p id="viewer-caption" class="viewer-caption"></p>
    <div id="viewer-meta" class="viewer-meta"></div>
    <a id="viewer-download" class="viewer-download" download>Download STEP</a>
  </div>
</div>
<script src="../scripts/viewer.ts"></script>
```

- [ ] **Step 2: Write the three.js viewer script**

Create `web/src/scripts/viewer.ts`:
```ts
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import models from "../data/models.json";

type Model = (typeof models)[number];
const byId = new Map<string, Model>(models.map((m) => [m.id, m]));

const modal = document.querySelector<HTMLElement>("#viewer-modal")!;
const canvasHost = document.querySelector<HTMLElement>("#viewer-canvas")!;
const captionEl = document.querySelector<HTMLElement>("#viewer-caption")!;
const metaEl = document.querySelector<HTMLElement>("#viewer-meta")!;
const downloadEl = document.querySelector<HTMLAnchorElement>("#viewer-download")!;

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

function showError() {
  canvasHost.innerHTML = '<p class="viewer-error">3D preview unavailable</p>';
}

function open(model: Model) {
  captionEl.textContent = model.caption;
  metaEl.innerHTML =
    `<span>${model.probe.n_faces} faces</span>` +
    `<span>${model.probe.n_solids} solid</span>` +
    `<span>ratio ${model.probe.bbox_ratio}</span>`;
  downloadEl.href = model.step;
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

  new GLTFLoader().load(
    model.glb,
    (gltf) => {
      const obj = gltf.scene;
      const box = new THREE.Box3().setFromObject(obj);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      obj.position.sub(center);
      const radius = Math.max(size.x, size.y, size.z) || 1;
      camera.position.set(radius * 1.6, radius * 1.2, radius * 1.8);
      controls!.target.set(0, 0, 0);
      controls!.update();
      scene.add(obj);
    },
    undefined,
    () => showError()
  );

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

- [ ] **Step 3: Add modal styles**

Append to `web/src/styles/global.css`:
```css
.modal { position: fixed; inset: 0; display: grid; place-items: center; z-index: 10; }
.modal[hidden] { display: none; }
.modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.5); }
.modal-body { position: relative; background: #fff; border-radius: 10px; padding: 1.25rem; max-width: 560px; width: 90%; }
.modal-close { position: absolute; top: 0.5rem; right: 0.75rem; border: none; background: none; font-size: 1.5rem; cursor: pointer; }
.viewer-canvas { width: 100%; min-height: 360px; background: #f4f6f8; border-radius: 6px; }
.viewer-error { text-align: center; padding: 4rem 0; color: #a33; }
.viewer-caption { margin: 0.75rem 0 0.5rem; font-size: 0.95rem; }
.viewer-meta { display: flex; gap: 0.5rem; font-size: 0.75rem; color: #567; }
.viewer-meta span { background: #eef2f5; border-radius: 4px; padding: 0.1rem 0.5rem; }
.viewer-download { display: inline-block; margin-top: 0.9rem; background: #1a2530; color: #fff; padding: 0.45rem 1rem; border-radius: 6px; text-decoration: none; font-size: 0.85rem; }
```

- [ ] **Step 4: Mount the modal on the page**

In `web/src/pages/index.astro` add the import and place `<ViewerModal />` at the end of `<body>`:
```astro
---
import "../styles/global.css";
import SearchBar from "../components/SearchBar.astro";
import ResultsGrid from "../components/ResultsGrid.astro";
import ViewerModal from "../components/ViewerModal.astro";
---
```
and just before `</body>`:
```astro
    <ViewerModal />
```

- [ ] **Step 5: Verify build + grid test + manual viewer check**

Run:
```bash
cd web && npm run build && node --test test/ ; cd ..
```
Expected: build succeeds, grid test PASSES. Then `cd web && npm run dev`: click a card → modal opens with a rotatable 3D model; Download STEP downloads the `.step`; Esc closes. If a GLB fails, the modal shows "3D preview unavailable" and the page keeps working.

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat: three.js modal viewer with orbit controls + download STEP"
```

---

## Self-Review

**Spec coverage:**
- Static Astro site, no backend/ML → Task 1, Global Constraints. ✓
- Text/sketch/image inputs, all cosmetic, uploads ignored → Task 4. ✓
- Hardcoded search returns same fixed list → Task 4 (`runSearch` just reveals the static grid). ✓
- 5 self-generated models via build123d → Task 2. ✓
- Asset split (binaries in public, json in src/data) → Task 2 interfaces + Task 3 import. ✓
- Results grid: thumbnail, caption, score, probe chips → Task 3. ✓
- Modal three.js viewer (orbit) + full caption/metadata + Download STEP → Task 5. ✓
- Error handling: GLB load failure placeholder, models.json malformed caught at build → Task 5 `showError`, build-time JSON import. ✓
- Testing: generator self-check, `astro build`, one grid component test → Task 2 `_self_check`, Tasks 3-5 build runs, Task 3 `grid.test.mjs`. ✓
- PNG via matplotlib (headless, no GL) → Task 2 `render_png`. ✓ (design refinement over the spec's unspecified renderer; spec ponytail note anticipated this.)

**Placeholder scan:** No TBD/TODO; all code blocks complete; `quality_flags` shown empty per part. ✓

**Type consistency:** `model-card` class + `data-model-id` defined in Task 3, consumed in Task 5. `models.json` field names consistent across Tasks 2/3/5 (`id`, `caption`, `glb`, `step`, `thumb`, `score`, `probe.{n_faces,n_solids,bbox_ratio,quality_flags}`). `runSearch`/`setMode` defined and used within Task 4. ✓
