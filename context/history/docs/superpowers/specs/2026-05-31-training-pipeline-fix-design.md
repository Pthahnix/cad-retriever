# CAD Sketch Retriever — Training Pipeline Fix Design

## Problem Statement

The current system produces recall@1=0, recall@10=0, MRR≈0. Three root causes:

1. **Phase 1 loss causes embedding collapse** — ViewConsistencyLoss only pulls same-model views together without pushing different models apart. The projection head learns to map everything to a constant vector.
2. **SketchEncoder LoRA gradients are blocked** — `torch.no_grad()` wraps the visual backbone in `SketchEncoder.forward()`, preventing LoRA parameters from receiving gradients during Phase 2 training.
3. **Render quality is unusable** — PIL polygon drawing with 1000 randomly sampled faces produces images that CLIP cannot extract meaningful features from.

## Solution Overview

- Replace rendering pipeline with pyrender + EGL GPU offscreen rendering
- Replace sketch generation with Canny edge detection + sketch perturbation (original plan)
- Replace Phase 1 loss with InfoNCE + Hard Negative Mining
- Fix SketchEncoder to allow LoRA gradient flow
- Wipe all existing rendered data and regenerate from scratch

## Execution Environment

- AutoDL pod: RTX 5090, 2TB data disk at `/home/cc/data`
- Python 3.12 via miniconda3
- New CC session will execute the plan via `superpowers:executing-plans`

---

## Change 1: Rendering Pipeline (pyrender + EGL)

### What changes

Replace `scripts/render_all.py` entirely. The current implementation uses PIL to draw polygons from 1000 randomly sampled mesh faces — this produces toy-quality silhouettes that CLIP cannot interpret.

### New approach

- **Library:** trimesh + pyrender with EGL backend (GPU offscreen, no display needed)
- **Material:** flat grey (0.6, 0.6, 0.6) metallic surface, white background
- **Lighting:** single directional light + ambient
- **Resolution:** 224×224 PNG
- **Views:** 6 standard angles — same elevation ring as before: `[(30,0), (30,60), (30,120), (30,180), (30,240), (30,300)]`
- **Mesh loading:** trimesh reads the STL exported from OCP (same STEP→STL path as current code)
- **Parallelism:** multiprocessing Pool with 8-16 workers, each worker holds its own pyrender.OffscreenRenderer
- **Timeout:** 10s per model, skip on failure
- **Temp file cleanup:** STL written to `/home/cc/data/tmp/` (NOT `/tmp/`), deleted immediately after mesh load

### Dependencies to install

```bash
pip install pyrender PyOpenGL PyOpenGL_accelerate
apt-get install -y libegl1-mesa-dev libgles2-mesa-dev
```

### Environment variable

```bash
export PYOPENGL_PLATFORM=egl
```

### Expected throughput

~30-80 models/sec with 16 workers on RTX 5090. Full 1M in 3.5-9 hours.

---

## Change 2: Sketch Generation (Canny + Perturbation)

### What changes

Replace `src/cad_retriever/data/edge_detect.py` — currently uses CLAHE contrast enhancement which produces grey-tone images, not edge maps.

### New approach

- **Edge detection:** Canny with auto-threshold (Otsu or median-based). With proper pyrender output (grey object on white background), Canny will produce clean edge lines.
- **Pre-processing before Canny:** convert to grayscale, Gaussian blur (σ=1.0) to reduce noise, then Canny with thresholds derived from median intensity: `low = 0.33 * median`, `high = 0.66 * median`.
- **Output:** binary edge map (white edges on black background), saved as 8-bit grayscale PNG.

### Sketch synthesis (unchanged from original plan)

`sketch_synth.py` stays the same — it applies perturbations to edge maps:
- Gaussian blur (line jitter)
- Random line breaks
- Thickness variation via dilation
- Partial occlusion via random rectangles

This simulates real hand-drawn sketches at various difficulty levels (0.2-0.8).

---

## Change 3: Phase 1 Training — InfoNCE + Hard Negative Mining

### What changes

Replace `src/cad_retriever/training/train_phase1.py`. The current ViewConsistencyLoss only minimizes variance across views of the same model without any contrastive signal.

### New Phase 1 training loop

**Objective:** Train the CAD projection head so that multi-view embeddings of the same model are similar, while embeddings of different models are dissimilar.

**Loss:** InfoNCE (symmetric). For each model in the batch:
- Positive pairs: different views of the same model
- Negative pairs: views of all other models in the batch

**Concrete formulation:**
- For each model, randomly pick 2 views → encode both → one is query, one is key
- The other models' views in the batch serve as negatives
- Symmetric cross-entropy on the similarity matrix

**Training schedule:**
- Phase 1a: InfoNCE for 5 epochs, batch_size=256, lr=1e-3
- After Phase 1a: compute all embeddings, mine hard negatives (rank 5-20 nearest neighbors)
- Phase 1b: InfoNCE with hard negative sampling for 5 epochs, batch_size=256, lr=5e-4

**Hard Negative Mining:**
- After Phase 1a converges, embed all models with current projection head
- For each model, find its top-20 nearest neighbors in embedding space
- Rank 5-20 are "hard negatives" (too close but not the same model)
- Phase 1b uses a modified DataLoader that ensures each batch contains the anchor model + its hard negatives

### Dataset change for Phase 1

Current `Phase1Dataset` returns all 6 views. New version returns 2 randomly sampled views per model (for the contrastive pair), which allows larger effective batch size.

---

## Change 4: SketchEncoder LoRA Fix

### What changes

`src/cad_retriever/models/encoder.py` line 60-61:

```python
# BEFORE (broken):
def forward(self, x):
    with torch.no_grad():        # ← blocks LoRA gradients!
        feats = self.visual(x)
    out = self.projection(feats)
    return nn.functional.normalize(out, dim=-1)

# AFTER (fixed):
def forward(self, x):
    feats = self.visual(x)       # ← LoRA params get gradients
    out = self.projection(feats)
    return nn.functional.normalize(out, dim=-1)
```

The frozen backbone weights still don't get gradients (they have `requires_grad=False`). Only the LoRA adapter parameters (which have `requires_grad=True`) will receive gradients. This is the correct behavior.

---

## Change 5: Phase 2 Training Adjustments

### What changes

Minor fixes to `train_phase2.py`:
- Batch size: 128 (down from 256) since LoRA now needs gradients through full backbone → more VRAM
- Epochs: 10 (unchanged)
- Add gradient clipping: `max_norm=1.0` to stabilize LoRA training
- Log loss per epoch + save best checkpoint (by validation loss on held-out 5%)

---

## Change 6: Data Cleanup

### Before starting the new pipeline

```bash
rm -rf /home/cc/data/renders
rm -rf /home/cc/data/edges
rm -rf /home/cc/data/sketches
rm -rf /home/cc/data/embeddings
rm -f /home/cc/data/cad.index
rm -f /home/cc/data/projection_head_a.pt
rm -f /home/cc/data/sketch_encoder.pt
rm -f /home/cc/data/eval_results.json
rm -f /home/cc/data/good_model_ids.txt
rm -f /home/cc/data/embedded_model_ids.txt
```

Keep: `abc_step/` (the STEP files), `model_ids.txt`, `blender-*` directory.

---

## Full Pipeline Execution Order

```
1. Install deps (pyrender, EGL)
2. Clean old data
3. Render all 1M models (pyrender + EGL) → /home/cc/data/renders/
4. Preprocess all (Canny edge + sketch synth) → /home/cc/data/edges/, /home/cc/data/sketches/
5. Phase 1a training (InfoNCE, 5 epochs)
6. Embed all (intermediate) → /home/cc/data/embeddings/
7. Hard negative mining → /home/cc/data/hard_negatives.json
8. Phase 1b training (InfoNCE + HN, 5 epochs)
9. Embed all (final) → /home/cc/data/embeddings/ (overwrite)
10. Build FAISS index → /home/cc/data/cad.index
11. Phase 2 training (LoRA + projection, 10 epochs) → /home/cc/data/sketch_encoder.pt
12. Evaluate → recall@1 >= 0.60, recall@10 >= 0.90, MRR >= 0.70
13. Deploy FastAPI serving endpoint
```

---

## Success Criteria

- recall@1 >= 0.60
- recall@10 >= 0.90
- MRR >= 0.70
- Serving endpoint responds to sketch queries in <10ms (FAISS search time)
- All 1M models rendered, preprocessed, embedded, and indexed

## Fallback Plan

If after full training recall targets are not met:
1. Increase Phase 1 epochs (10 → 20)
2. Increase LoRA rank (16 → 32)
3. Use larger CLIP model (ViT-B/16 → ViT-L/14)
4. Add data augmentation to Phase 2 (rotation, scale, translation on sketches)
