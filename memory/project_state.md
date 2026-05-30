---
name: project-state
description: Current pipeline execution state — what's done, what's running, what's next
metadata:
  type: project
---
All 13 code tasks implemented and 30/30 tests passing. Committed and pushed to origin/main.

ABC Dataset download running in background (PID 13114/13115) since 16:40 CST 2026-05-30.
- Download log: /home/cc/data/download.log
- Chunks dir: /home/cc/data/abc_step/chunks/ (100 chunks, ~300MB each, ~30GB total)
- Expected completion: ~18:45 CST 2026-05-30
- 8 parallel curl downloads via proxy http://127.0.0.1:7890

After download completes, pipeline runs in order:
1. Extract chunks → /home/cc/data/abc_step/step/ (done by download.py)
2. Render all 1M models → /home/cc/data/renders/ (scripts/render_all.py)
3. Preprocess → /home/cc/data/edges/, /home/cc/data/sketches/ (scripts/preprocess_all.py)
4. Phase 1 train → /home/cc/data/projection_head_a.pt (scripts/train.py --phase 1)
5. Embed all → /home/cc/data/embeddings/ (scripts/embed_all.py)
6. Build FAISS index → /home/cc/data/cad.index (scripts/build_index.py)
7. Phase 2 train → /home/cc/data/sketch_encoder.pt (scripts/train.py --phase 2)
8. Evaluate → targets: recall@1>=0.60, recall@10>=0.90, MRR>=0.70
9. Serve → uvicorn on port 8000

**Why:** Full pipeline must run end-to-end per CLAUDE.md requirements.
**How to apply:** After download completes, run scripts/run_pipeline.py --skip-download --data-root /home/cc/data
