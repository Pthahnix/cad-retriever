# CAD Retriever Presentation — Design Spec

**Date:** 2026-06-23
**Status:** Approved
**Author:** brainstormed with user

## Goal

Build an Astro-based presentation (not plain HTML) for the CAD Retriever project. It keeps PPT-style page-switching transitions, but each slide is a long, scrollable blog-style page packed with content, figures, and HTML/CSS/JS visualizations. One slide embeds the live, interactive web app (natively, by reusing the existing Astro components). The web app's UI is restyled to match the presentation's lo-fi cyberpunk palette so the demo slide is visually unified with the deck.

## Scope

In scope:
- New Astro project under `presentations/cad-retriever/` (separate from `web/`).
- 5 slides, single-page full-screen stacked-section navigation model.
- Restyle the existing `web/` UI to the new palette (this is a real change to `web/`, not a copy-only restyle).
- Embed the (restyled) web app components natively into the demo slide.

Out of scope:
- Backend integration (FAISS retrieval, GLB loading) — the demo stays cosmetic/hardcoded as it is today.
- PDF export (browser print-to-PDF is acceptable).
- Deployment.

## Navigation Architecture

**Model: single-page full-screen stacked sections** (fullPage.js style).

- One `src/pages/index.astro` containing 5 full-screen `<section>` elements stacked vertically.
- Each section: `height: 100vh; overflow-y: auto` — content beyond one screen scrolls within the section.
- Page switching: arrow keys / PageUp-PageDown / Space → `translateY` transition between sections (this is the PPT page-flip animation).
- Boundary auto-flip: when a section is scrolled to its top or bottom edge, continuing to scroll (wheel) past the edge triggers a flip to the adjacent section. Wheel events are throttled/debounced to avoid accidental multi-flips.
- A fixed progress bar / page indicator shows the current slide (e.g. `2 / 5`).
- Touch: swipe up/down to flip when at a scroll boundary; otherwise native touch scroll within the section.
- `@media print`: sections expand to full content height, stacked, page-break between them.

**Three scroll behaviors that must coexist:**
1. Within-page scroll (wheel / touch / arrow-when-not-at-boundary) → scrolls current section content.
2. Page flip (arrow keys / PageUp-Down / Space) → transition to next/prev section.
3. Boundary auto-flip (wheel past top/bottom edge) → transition to adjacent section.

**Rejected alternatives:**
- Multi-route + Astro View Transitions: cross-route long-scroll + auto-flip is awkward; transitions less controllable.
- keynova classic (absolute-positioned + opacity): fundamentally conflicts with long scrollable content.

## Visual System

**Style: Lo-fi Cyberpunk × Editorial "Annual Report"**

Palette (CSS variables):
- `--teal: #0D6E78` — primary
- `--rust: #C8300A` — accent / emphasis
- `--amber: #F5A800` — highlight / data callouts
- `--dark-green: #1A4D3C`
- `--mid-green: #2E6B4F`
- `--navy: #0A1A2E` — base background

Visual characteristics:
- Diagonal gradient backgrounds (teal → rust/amber).
- Large serif italic display headings (Playfair Display or DM Serif Display via Google Fonts).
- Rounded pill badges for eyebrow labels.
- Soft-shadow cards, 8–12px border radius.
- Subtle noise-texture overlay.
- Code blocks / data tables: dark background with teal border, rust-highlighted key lines.

Language: mixed Chinese/English — English titles, Chinese body, technical terms kept in original (InfoNCE, ControlNet, FAISS, STEP, etc.).

Content density: **rich** — 2–4 screens per slide, blog-style. Each slide has an overview paragraph plus multiple sub-sections, figures/diagrams/code blocks, and sidenotes/pull-quotes.

CJK font loading required (`Noto Sans SC` for body).

## Project Structure

```
presentations/cad-retriever/
├── package.json
├── astro.config.mjs
├── tsconfig.json
├── public/
│   └── (favicon, any static assets)
└── src/
    ├── pages/
    │   └── index.astro              # 5 stacked sections + nav wiring
    ├── layouts/
    │   └── Deck.astro               # <html>, head, fonts, global deck CSS, progress bar, nav script include
    ├── components/
    │   ├── slides/
    │   │   ├── Slide1Intro.astro    # Introduction & Problem Statement
    │   │   ├── Slide2Dataset.astro  # Dataset Preprocessing Pipeline
    │   │   ├── Slide3Quality.astro  # Quality Filtering Strategy
    │   │   ├── Slide4Arch.astro     # System Architecture
    │   │   └── Slide5Demo.astro     # Live Demo (embeds web app)
    │   ├── ui/                      # small reusable deck primitives
    │   │   ├── Pill.astro           # eyebrow badge
    │   │   ├── Card.astro           # soft-shadow rounded card
    │   │   ├── CodeBlock.astro      # dark code block w/ teal border
    │   │   └── StatBar.astro        # horizontal bar / metric viz
    │   └── webapp/                  # the embedded app (restyled copies)
    │       ├── SearchBar.astro
    │       ├── ResultsGrid.astro
    │       ├── ModelCard.astro
    │       └── ViewerModal.astro
    ├── scripts/
    │   ├── deck-nav.ts              # keyboard + wheel-boundary + touch + progress
    │   └── webapp/                  # copied + adapted from web/src/scripts
    │       ├── search.ts
    │       ├── shapes.ts
    │       ├── thumbs.ts
    │       └── viewer.ts
    ├── data/
    │   └── models.json              # copied from web/src/data
    └── styles/
        ├── deck.css                 # presentation base + theme variables
        ├── webapp.css               # restyled web app CSS, scoped under #demo-slide
        └── figures.css              # diagram/chart styling
```

## Web App Restyle (applies to BOTH `web/` and the embedded copy)

The user requires the live `web/` app's UI restyled to the lo-fi cyberpunk palette, and the demo slide shows that same restyled app. To avoid divergence:

- The canonical restyle lands in `web/src/styles/global.css` (and component markup if needed).
- The presentation's `src/styles/webapp.css` is the same restyle, scoped under a `#demo-slide` parent selector so it cannot leak into deck chrome.

Restyle mapping (from current light theme → new palette):
- Page/app background → `--navy` or diagonal dark gradient.
- `.searchbox` border → `--teal`; `:focus-within` glow → rust/amber.
- `.go-btn` → `--teal` bg / white text; hover → `--rust`.
- `.results tbody tr:hover` → teal at ~10% alpha.
- `.score` → `--amber`.
- `.flag` → rust-tinted pill.
- `.thumb` border → `--teal`.
- `.modal-body` → dark surface; `.viewer-canvas` border → `--teal`; `.viewer-meta span` → pill style.
- Text colors adjusted for dark background contrast (WCAG AA target for body text).

## CSS Isolation

- Deck chrome uses `deck-*` / `slide-*` class prefixes and theme CSS variables.
- Web app keeps its original class names (`.searchbox`, `.results`, `.modal`, etc.) but all its CSS is scoped under `#demo-slide` in the presentation so it never collides with deck styles.
- Theme palette variables are defined once at `:root` and shared by both deck and webapp CSS.

## Demo Embedding

- Slide 5 (`Slide5Demo.astro`) renders the restyled `webapp/` components natively (no iframe): `SearchBar` + `ResultsGrid` + `ViewerModal`, wrapped in a `<div id="demo-slide">`.
- All interactivity preserved: text input, sketch/image upload, mode tag switching, results table, click-to-open 3D viewer modal with OrbitControls and geometry metadata.
- `three` is a dependency of the presentation project (same version as `web/`: `^0.184.0`).
- A short intro line above the app: "Interactive Demo — try text / sketch / image search".
- A floating hint bottom-right: "Press ↑ ↓ to navigate slides" (and a note that the demo is interactive).
- Edge case: the 3D modal is `position: fixed; inset: 0` — it must overlay the whole viewport above the deck, not be clipped by the section's `overflow-y: auto`. The modal is appended at deck root level (or uses a high z-index above section stacking) so it is not clipped.
- Edge case: while the demo modal is open or an input is focused, deck keyboard navigation (arrows) must be suppressed so typing/orbiting doesn't flip slides. `deck-nav.ts` checks `document.activeElement` (ignore when it's an input/textarea) and a "modal open" flag.

## Slide Content

Each slide targets 2–4 screens of rich, blog-style content.

### Slide 1 — Introduction & Problem Statement
(cover + problem statement merged; content preserved in full)

1. Hero banner: title "CAD Retriever" + subtitle "Multimodal Neural Search for Mechanical Parts" + eyebrow pill "Research Demo · 2026".
2. Three-modality diagram: 3 cards (Text natural-language box / Sketch hand-drawn / Image reference) with arrows converging to a center "Shared Embedding Space".
3. Problem statement: traditional CAD retrieval pain points — relies on filename/metadata, cannot understand shape semantics.
4. Engineer use-case cards: "find similar part to replace" / "find existing part from a sketch" / "reverse-search from a reference image".
5. Technical challenges: multimodal alignment / large-scale dataset / real-time retrieval.

Visual: diagonal teal→amber gradient background, serif italic hero title, modality cards with icons.

### Slide 2 — Dataset Preprocessing Pipeline

1. Dataset overview: ABC Dataset — 1M STEP files, ~500GB, source CVPR 2019 (Koch et al.).
2. Pipeline overview diagram: STEP → Multi-view Rendering → Sketch Generation → Text Annotation, each step labeled with its time cost.
3. Multi-view Rendering:
   - Stack: Blender headless + EEVEE GPU.
   - 30-view strategy: 10 azimuth × 3 elevation. Azimuth 0/36/72/108/144/180/216/252/288/324°; elevation 15/35/60°. Figure: top-view ring of 10 dots + side-view 3 layers.
   - Output: 224×224 JPEG q90, 30M images, ~625GB.
   - Time: ~60h on 1× RTX 5090.
4. Sketch Generation:
   - Stack: SDXL-Lightning 4-step (HF ByteDance/SDXL-Lightning) + ControlNet Lineart (HF xinsir/controlnet-scribble-sdxl-1.0) + controlnet_aux LineartDetector.
   - 6-view sampled from the 30 views.
   - Output: 6M grayscale JPEG, ~40GB.
   - Time: ~144h on 1× RTX 5090.
5. Text Annotation:
   - VLM: Qwen3.6-27B, multi-image input (all 30 views).
   - Prompt: shape-centric, referencing NURBGen partABC (~300K captions, arXiv 2511.06194) style.
   - Example caption: "a flat cylindrical disc with a central through-hole and six evenly spaced mounting holes".
   - 27B fp16 ~54GB, needs 2× RTX 5090.
   - Output: 1M JSON, ~1GB. Time: ~16h on 2× RTX 5090.
6. Total time comparison chart: horizontal bars — Rendering 60h / Sketch 144h / Annotation 16h.

Visual: teal-arrow flow diagram, per-step code blocks for the stack, amber-highlighted time numbers.

### Slide 3 — Quality Filtering Strategy

1. Lesson learned: previous run stalled at 276K/990K; implicit timeout filtering uncontrollable; training set forced down to 340K.
2. Design goal: move quality filtering from a render-timeout byproduct to an explicit, cheap, interpretable, reproducible pre-render step. Filtering does not delete files — it writes a `quality_flags` column to the manifest so excluded models can be queried and reviewed.
3. Four-phase strategy (table):

   | Phase | Cost | Checks | Flags |
   |-------|------|--------|-------|
   | 1. Metadata | zero-parse | file_size > 50MB / ≈0; ABC `*_features.yml` if present | `oversized` / `corrupt` |
   | 2. Topology probe | sub-second, no mesh | ReadFile != 1; n_faces > 5000 / < 3; n_solids == 0; bbox dim ≈ 0; bbox ratio > 1000:1 | `step_read_fail` / `too_complex` / `too_simple` / `no_solid` / `degenerate` |
   | 3. Image-level | cheap (post-render, optional) | foreground pixels < 1%; very low inter-view variance | `blank_render` / `low_variance` |
   | 4. Semantic dedup | later (CLIP) | cosine-similarity near-duplicate; diversity sampling | (dedup marks) |

4. Topology-probe technical detail: pseudocode code block —
   ```python
   reader = STEPControl_Reader()
   if reader.ReadFile(step_path) != 1: flag = "step_read_fail"
   explorer = TopExp_Explorer(shape, TopAbs_FACE)   # no BRepMesh
   n_faces = count(explorer)
   if n_faces > 5000: flag = "too_complex"
   ```
5. Manifest new columns: `probe_n_faces`, `probe_n_solids`, `probe_bbox_ratio`, `file_size_mb`, `quality_flags`.
6. Pending directional decision (pull-quote): part-level vs assembly-level retrieval? Determines whether `n_solids > 1` is filtered out or specially handled (slow render queue with longer timeout + lower mesh precision).
7. Filtering funnel visualization: funnel/Sankey — 1M → metadata filter → topology filter → image filter → final eligible count. Note: exact eligible count is unknown until the probe runs (thresholds set from the histogram, not guessed); render the funnel with the categories and label the final number as illustrative/TBD-from-probe rather than a fabricated figure.

Visual: teal-bordered table, dark code block with rust-highlighted key line, gradient-filled funnel.

### Slide 4 — System Architecture

1. Architecture overview diagram (layered): Frontend (Astro + three.js) → Embedding Model (Contrastive Learning, InfoNCE + hard negative mining) → Backend (FAISS vector DB) → Data (ABC 1M preprocessed: renders + sketches + captions).
2. Contrastive Learning: InfoNCE loss (formula via KaTeX or figure); hard negative mining strategy; shared embedding space diagram (Text/Sketch/Image projected into one latent space).
3. Frontend stack cards: Astro, three.js 3D viewer, OrbitControls, real-time thumbnail rendering.
4. Backend stack cards: FAISS index type (IVF / HNSW), embedding dimension, retrieval latency target.
5. Data flow sequence: User input → Encode → Query FAISS → Retrieve top-K → Render 3D + metadata.
6. Performance metrics table (with bar viz): embedding inference, FAISS retrieval, 3D model loading, total latency — labeled as **design targets**, not measured results.

Visual: layered rectangles + arrows, amber-background formula callout, progress-bar metric viz.

Note: architecture specifics (loss = InfoNCE, hard negative mining, FAISS, contrastive shared space) come from prior project context and are stated as the intended/planned design. Any numbers not grounded in the cost-estimate doc are presented as targets, not claims.

### Slide 5 — Live Demo

Full-page embed of the restyled web app (see Demo Embedding and Web App Restyle above).

1. Intro line: "Interactive Demo — try text / sketch / image search".
2. The restyled app: SearchBar + ResultsGrid + ViewerModal, fully interactive (5 hardcoded demo models, cosmetic latency, click-to-open 3D viewer).
3. Floating navigation hint bottom-right.

Visual: the climax slide; the only interactive page; dark palette matching the deck.

## Dev / Preview

- `npm install` then `astro dev` (per `web/CLAUDE.md`, use background mode: `astro dev --background`; manage with `astro dev stop/status/logs`).
- Default Astro dev port 4321.
- Build: `astro build`; preview: `astro preview`.

## Testing / Verification

- Build must succeed (`astro build`) with no errors before completion.
- Manual verification of the three scroll behaviors: within-page scroll, arrow/PageUp-Down flip, wheel-boundary auto-flip.
- Manual verification that demo-slide keyboard suppression works (typing in the search box and orbiting the 3D model do not flip slides).
- Manual verification that the 3D modal overlays the full viewport and is not clipped by section overflow.
- A small runnable check for `deck-nav.ts` boundary logic (the non-trivial piece): a unit test for the "at top/bottom edge?" + throttle decision, mirroring the existing `web/test/grid.test.mjs` node-test style. No framework beyond node's built-in test runner.

## Open Questions / Deferred

- Exact eligible count after quality filtering: unknown until probe runs — shown as illustrative.
- Backend performance numbers: shown as targets.
- Per-page content can be fine-tuned slide-by-slide after first generation (user reserved this).
