# CAD Retriever Demo Web App — Design

> Date: 2026-06-22
> Status: design complete, pending implementation
> Scope: a self-contained static web app that *demonstrates* cross-modal CAD retrieval.
> Not in scope: the real retrieval model, real pipeline outputs, any backend or ML inference.

---

## 1. Goal & framing

Build a demo website that makes `cad-retriever` look like a finished, working
cross-modal CAD search engine — a visitor types a text description (or uploads a
sketch / image) and gets back matching CAD models they can inspect in 3D.

**Key framing constraint:** the real pipeline (download → probe → render → sketch →
caption → embedding) is *pretend complete*. No dataset, renders, captions, or
embeddings exist locally. So the demo ships its own tiny self-generated dataset and
**fakes the retrieval**: search is hardcoded and always returns the same ranked list.
The input widgets are real and interactive; the ranking is a constant. This is a
deliberate, honest demo shortcut — not a real retriever.

---

## 2. Architecture

A **static Astro site** — no backend, no database, no ML. Everything is baked at
build time and served as static files.

- **Astro** renders the page shell and all static content (ships ~zero JS by default).
- **Two small client islands**: the **three.js viewer** (the real interactive piece)
  and the **search bar** (trivial — any input shows the one fixed result set). Astro
  static-renders everything else.
- **three.js** + `GLTFLoader` + `OrbitControls` for the 3D model viewer (rotate / zoom / pan).
- **Demo data is 5 self-generated CAD models.** A one-shot Python generator authors
  them and exports the assets the site consumes.

### Two decoupled units

| Unit | What it does | Language | Run when |
|---|---|---|---|
| `demo-assets/generate.py` | Defines 5 parametric CAD parts, exports `.step` / `.glb` / `.png` per part, writes `models.json`. | Python (build123d) | Manually, once (or when models change). |
| `web/` | Astro app. Reads the generated assets from `public/`, renders the search UI + results + 3D viewer. | TypeScript / Astro | `astro dev` / `astro build`. |

They communicate only through files in `web/public/models/`. The web app never
computes anything — it only reads what the generator produced.

---

## 3. Pages & layout

**Single page, one route.** Three zones, top to bottom:

1. **Search bar** (top)
   - A text input with three mode tabs: `Text · Sketch · Image`.
   - Text mode: a normal text box.
   - Sketch / Image mode: an upload (or draw) widget. The upload is accepted but its
     contents are ignored — it triggers the same hardcoded result.
   - A row of suggested example queries so a visitor doesn't have to think of one.
   - Any input (any mode) returns the same fixed ranked list.

2. **Results grid** (middle)
   - The 5 models as cards in fixed rank order.
   - Each card: thumbnail render (`.png`), caption, a faked similarity score
     (e.g. 0.94 / 0.89 …, descending), and probe-metadata chips
     (`n_faces`, `n_solids`, `quality_flags`).

3. **Detail viewer** (modal popup)
   - Clicking a card opens a modal with the **three.js viewer** for that model
     (rotate / zoom / pan), its full caption, full metadata, and a **Download STEP** link.
   - Esc or click-outside closes the modal.
   - Modal chosen over a bottom panel: with only 5 cards it keeps the grid visible
     and avoids a long scroll.

---

## 4. Data shape

One file, `web/public/models/models.json` — an array of 5 entries:

```json
{
  "id": "demo/0001",
  "caption": "a flat cylindrical disc with a central through-hole and six evenly spaced mounting holes",
  "glb": "/models/0001.glb",
  "step": "/models/0001.step",
  "thumb": "/models/0001.png",
  "score": 0.94,
  "probe": { "n_faces": 14, "n_solids": 1, "bbox_ratio": 3.2, "quality_flags": [] }
}
```

The `.glb` / `.step` / `.png` files and this JSON are all produced by the generator.
`score` and `probe` are authored values that mimic real pipeline output — they make
the cards look like genuine retrieval results.

---

## 5. The generator (`demo-assets/generate.py`)

A one-shot Python script, run manually, **not** part of the site build. It defines 5
**visually distinct** parametric parts with **build123d** so the demo reads well —
e.g. flanged disc with holes, L-bracket, hex nut, stepped shaft, ribbed plate.

For each part it exports into `web/public/models/`:
- `NNNN.step` — real CAD file, for the download link.
- `NNNN.glb` — mesh for the three.js viewer.
- `NNNN.png` — thumbnail for the result card.

and writes `models.json` with captions + faked `score` + faked `probe` metadata.

> ponytail note: the thumbnail `.png` could be skipped by rendering each GLB in a tiny
> static three.js canvas in the grid. Baking a PNG is simpler and lighter than mounting
> 5 mini-viewers, so PNG stays. Add the in-grid live preview only if PNGs prove a problem.

---

## 6. Error handling

It's a static site, so little can fail at runtime. The cases that matter:

- **GLB fails to load in the viewer** → show a "preview unavailable" placeholder inside
  the modal; the rest of the card/page keeps working.
- **`models.json` missing or malformed** → caught at build time (`astro build` fails
  loudly), not in the browser.

No network/auth/runtime-data failure modes exist because there is no backend.

---

## 7. Testing

Scaled to a demo — one runnable check per non-trivial unit, no e2e suite.

- **Generator:** one assert-based self-check (run after generation) that all 5 models
  produced a `.step`, `.glb`, and `.png`, and that `models.json` parses to 5 valid
  entries with the required fields.
- **Web app:** `astro build` is the primary check — it fails on broken imports or
  malformed data. Plus one light component test that the results grid renders 5 cards
  from `models.json`.

---

## 8. Tech / environment notes

- **Node.js** + npm/pnpm for Astro (`npm create astro@latest` is the first build step).
- **three.js** added via npm to the Astro project.
- **Python** with **build123d** for the generator (exports STEP + GLB + PNG). This is
  separate from the main `cad_pipeline` package and has no dependency on it.
- Astro is a *framework installed into the project*, not a Claude skill — installing it
  is the first implementation step, done after this spec is approved.

---

## 9. Deliverables

1. `demo-assets/generate.py` + its 5 generated parts and `models.json`.
2. `web/` — a static Astro site with search UI, results grid, and three.js modal viewer.
3. A `astro build` that produces a deployable static site demonstrating cross-modal
   CAD retrieval over the 5 demo models.
