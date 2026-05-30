#!/usr/bin/env python3
"""
Full pipeline orchestration script.
Runs all steps sequentially after download completes.
Usage: python3 scripts/run_pipeline.py --data-root /home/cc/data
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path


def run(cmd: list, desc: str):
    print(f"\n{'='*60}")
    print(f"STEP: {desc}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, check=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-preprocess", action="store_true")
    parser.add_argument("--skip-phase1", action="store_true")
    parser.add_argument("--skip-embed", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--skip-phase2", action="store_true")
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()

    dr = str(args.data_root)
    py = sys.executable

    if not args.skip_download:
        run([py, "scripts/download_abc.py", "--output", f"{dr}/abc_step"],
            "Download ABC Dataset (1M STEP files)")

    if not args.skip_render:
        run([py, "scripts/render_all.py",
             "--input", f"{dr}/abc_step/step",
             "--output", f"{dr}/renders"],
            "Render all 1M models (6 views each)")

    if not args.skip_preprocess:
        run([py, "scripts/preprocess_all.py",
             "--renders", f"{dr}/renders",
             "--edges-out", f"{dr}/edges",
             "--sketches-out", f"{dr}/sketches"],
            "Generate edge maps and synthetic sketches")

    if not args.skip_phase1:
        run([py, "scripts/train.py", "--phase", "1", "--data-root", dr],
            "Phase 1: Train CAD projection head")

    if not args.skip_embed:
        run([py, "scripts/embed_all.py", "--data-root", dr],
            "Compute all 1M CAD embeddings")

    if not args.skip_index:
        run([py, "scripts/build_index.py", "--data-root", dr],
            "Build FAISS index")

    if not args.skip_phase2:
        run([py, "scripts/train.py", "--phase", "2", "--data-root", dr,
             "--epochs", str(args.epochs)],
            "Phase 2: Train sketch encoder")

    run([py, "scripts/evaluate.py", "--data-root", dr],
        "Evaluate on test set")

    print("\n" + "="*60)
    print("Pipeline complete! Starting serving endpoint...")
    print("="*60)
    subprocess.run([py, "-m", "uvicorn",
                    "cad_retriever.serving.app:create_app",
                    "--factory",
                    "--host", "0.0.0.0",
                    "--port", "8000"])


if __name__ == "__main__":
    main()
