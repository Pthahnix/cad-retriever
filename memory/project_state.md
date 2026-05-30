---
name: project-state
description: Current pipeline execution state — what's done, what's running, what's next
metadata:
  type: project
---
All 13 code tasks implemented and 30/30 tests passing. Committed and pushed to origin/main.

**Current pipeline state (as of 2026-05-31 06:03 CST):**
- Rendering: 276K/990K (28%) at ~900/min → ETA ~13 hours (~19:00 CST)
- Preprocessing: 246K edges, keeping pace with rendering
- Monitor: running, auto-restarts render/preprocess if they crash
- Phase 1 training: waiting for 900K renders (monitor trigger)

**Key fixes applied:**
- render_all: Pool(maxtasksperchild=50) prevents BrokenProcessPool
- render_all: 30s SIGALRM timeout per model skips complex STEP files
- preprocess_all: continuous loop, waits for rendering to reach 95%
- monitor: auto-restarts render/preprocess if they die

**Pipeline sequence after rendering completes:**
1. Phase 1 train → projection_head_a.pt (monitor triggers at 900K renders)
2. embed_all → /home/cc/data/embeddings/ (monitor triggers after Phase 1)
3. build_index → /home/cc/data/cad.index (monitor triggers at 900K embeddings)
4. Phase 2 train → sketch_encoder.pt (monitor triggers after index)
5. serve → uvicorn port 8000 (monitor triggers after Phase 2)

**Why:** Full pipeline must run end-to-end per CLAUDE.md requirements.
**How to apply:** Monitor at /home/cc/data/monitor.log handles all triggers automatically.
