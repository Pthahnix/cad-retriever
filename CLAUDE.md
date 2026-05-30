# CLAUDE.md — CAD Sketch Retriever Project Rules

## Critical: Disk Usage

The system disk (`/`) is only 30GB with ~15GB free. It WILL fill up and crash the container if misused.

**ALL data MUST go to the data disk at `/home/cc/data/` (2TB, mounted from `/root/autodl-tmp`).**

This includes:
- Downloaded datasets (ABC STEP files, chunks, archives)
- Converted USD files
- Rendered images (6 views × 1M models = 6M PNGs)
- Edge maps and synthetic sketches
- Precomputed embeddings (.npy files)
- FAISS index files
- Model checkpoints and weights
- Training logs (wandb, tensorboard)
- Any temporary/intermediate files during processing

**NEVER write large files or datasets to:**
- `/home/cc/cad-retriever/data/` (this is on the system disk)
- `/tmp/` (system disk)
- Any path not under `/home/cc/data/`

The `Config.data_root` MUST be set to `/home/cc/data` when running any script:
```bash
python scripts/download_abc.py --output /home/cc/data/abc_step
python scripts/train.py --phase 1 --data-root /home/cc/data
python scripts/evaluate.py --data-root /home/cc/data
```

## Critical: Full Dataset — No Shortcuts

This project uses the **complete ABC Dataset (1,000,000 CAD models)**. The following rules are absolute:

1. **Download ALL 1M STEP files** before starting any conversion. Verify count >= 900,000.
2. **Convert ALL 1M models** to USD/mesh format before rendering. No sampling.
3. **Render ALL 1M models** (6 views each = 6M images) before preprocessing.
4. **Preprocess ALL 6M images** (edge detection + sketch synthesis) before training.
5. **Compute ALL 1M embeddings** before building the FAISS index.

**Do NOT:**
- Use a subset/sample "to test first" and then skip the full run
- Skip failed conversions/renders without logging them
- Reduce the dataset size to save time
- Stop a batch job early and proceed with partial data

If a step takes a long time (hours/days), that is expected. Let it run to completion. Use `nohup` and log progress.

## Critical: GPU Utilization

The pod has an **RTX 5090** — maximize its use:

- **Phase 1 training**: `batch_size_phase1 = 512` minimum. If GPU memory allows, increase to 1024.
- **Phase 2 training**: `batch_size_phase2 = 256` minimum. Increase if possible.
- **Embedding computation**: Use `batch_size = 128` or higher in `scripts/embed_all.py`.
- **FAISS index**: Use GPU-accelerated index building (`faiss.index_cpu_to_gpu`).
- Always use `pin_memory=True` and `num_workers=8` (or more) in DataLoaders.
- Use `torch.cuda.amp` (automatic mixed precision) for training to double throughput.
- Monitor GPU usage with `nvidia-smi` — utilization should be >80% during training/inference.

If you see GPU utilization below 50%, something is wrong (likely CPU-bound data loading). Fix it.

## Execution Pipeline Order

Strict sequential order — each step requires ALL data from the previous step:

```
Code (Tasks 1-8) → Download 1M → Convert 1M → Render 1M → Preprocess 1M
→ Phase 1 Train → Embed 1M → Build Index → Phase 2 Train → Evaluate → TRT → Serve
```

## Build & Test

```bash
# Run tests (from project root)
cd /home/cc/cad-retriever
pip install -e ".[dev]"
pytest tests/ -v

# Training
python scripts/train.py --phase 1 --data-root /home/cc/data
python scripts/train.py --phase 2 --data-root /home/cc/data --epochs 10

# Evaluation targets
# recall@1 >= 0.60, recall@10 >= 0.90, MRR >= 0.70
```

## Environment

- Python: use `/root/miniconda3/bin/python3` (Python 3.12)
- PATH must include: `/home/cc/.nvm/versions/node/v24.16.0/bin:/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`
- Proxy: `http_proxy=http://127.0.0.1:7890` (mihomo, required for GitHub/HuggingFace/PyPI)
- GPU: NVIDIA RTX 5090, CUDA available via PyTorch 2.8.0+cu128

## Critical: Self-Monitoring Cron

You MUST set up a recurring self-check every 30 minutes using Claude Code's built-in cron/scheduling capability. At the start of your session, create a cron that fires every 30 minutes with a prompt like:

```
Self-check: Am I still making progress? Review what I've done in the last 30 minutes. If I'm stuck, diagnose and fix. If a long-running process is active (download, training, rendering), verify it's still running and report progress. If I've finished all code tasks but haven't started the data pipeline, START IT NOW. My job is not done until the full pipeline has run end-to-end and I have a working, deployed service.
```

**Your job is NOT done when code is written.** Your job is done when:
1. All 13 code tasks are implemented and tests pass
2. The full 1M dataset is downloaded, converted, rendered, and preprocessed
3. Phase 1 and Phase 2 training have completed on the full dataset
4. Evaluation metrics meet targets (recall@1 >= 0.60, recall@10 >= 0.90, MRR >= 0.70)
5. The FAISS index is built from all 1M embeddings
6. The FastAPI serving endpoint is running and responding to queries
7. All work is committed and pushed

If you finish writing code and stop — you have failed. The deliverable is a **working, trained, deployed system**, not source code.

## Git Workflow

- Commit after each completed task
- Push all commits to origin (uses HTTPS with PAT credential store)
- Commit messages: `feat:`, `fix:`, `chore:` prefixes
