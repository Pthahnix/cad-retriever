#!/usr/bin/env python3
"""
Monitor pipeline progress and auto-start next steps.
Tracks: download → extraction → rendering → preprocess → train → embed → index → serve
"""
import time
import subprocess
import sys
from pathlib import Path

DATA_ROOT = Path("/home/cc/data")
CHUNKS_DIR = DATA_ROOT / "abc_step" / "chunks"
STEP_DIR = DATA_ROOT / "abc_step" / "step"
RENDERS_DIR = DATA_ROOT / "renders"
EDGES_DIR = DATA_ROOT / "edges"
SKETCHES_DIR = DATA_ROOT / "sketches"
EMBEDDINGS_DIR = DATA_ROOT / "embeddings"
PIPELINE_LOG = DATA_ROOT / "pipeline.log"
PYTHON = "/root/miniconda3/bin/python3"
SCRIPTS = "/home/cc/cad-retriever/scripts"
PYTHONPATH = "/home/cc/cad-retriever/src"


def run_bg(cmd, log_file):
    env = {"PATH": "/root/miniconda3/bin:/home/cc/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
           "PYTHONPATH": PYTHONPATH}
    import os
    full_env = {**os.environ, **env}
    with open(log_file, "a") as log:
        p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                             cwd="/home/cc/cad-retriever", env=full_env)
    return p.pid


def is_running(script_name):
    r = subprocess.run(["pgrep", "-f", script_name], capture_output=True)
    return r.returncode == 0


def count_files(directory, pattern):
    d = Path(directory)
    if not d.exists():
        return 0
    return sum(1 for _ in d.rglob(pattern))


def main():
    print("Pipeline monitor started.", flush=True)
    preprocess_started = False
    phase1_started = False
    embed_started = False
    index_started = False
    phase2_started = False
    serve_started = False

    while True:
        rendered = count_files(RENDERS_DIR, "view_5.png")
        step_files = count_files(STEP_DIR, "*.step")
        edges = count_files(EDGES_DIR, "view_5.png")
        embeddings = count_files(EMBEDDINGS_DIR, "*.npy")
        index_exists = (DATA_ROOT / "cad.index").exists()
        sketch_enc = (DATA_ROOT / "sketch_encoder.pt").exists()

        print(f"[{time.strftime('%H:%M:%S')}] "
              f"STEP:{step_files} | Rendered:{rendered} | "
              f"Edges:{edges} | Emb:{embeddings} | "
              f"Index:{index_exists} | SketchEnc:{sketch_enc}",
              flush=True)

        # Start preprocess when enough renders are done (or rendering is complete)
        if rendered >= 50000 and not preprocess_started and not is_running("preprocess_all"):
            print("Starting preprocess (edge detection + sketch synthesis)...", flush=True)
            pid = run_bg([PYTHON, f"{SCRIPTS}/preprocess_all.py",
                          "--renders", str(RENDERS_DIR),
                          "--edges-out", str(EDGES_DIR),
                          "--sketches-out", str(SKETCHES_DIR)],
                         DATA_ROOT / "preprocess.log")
            print(f"Preprocess PID: {pid}", flush=True)
            preprocess_started = True

        # Start Phase 1 training when rendering is substantially done
        if rendered >= 900000 and not phase1_started and not is_running("train.py"):
            # Write model_ids.txt first
            model_ids_path = DATA_ROOT / "model_ids.txt"
            if not model_ids_path.exists():
                step_files_list = sorted(Path(STEP_DIR).rglob("*.step"))
                model_ids_path.write_text("\n".join(f.stem for f in step_files_list))
            print("Starting Phase 1 training...", flush=True)
            pid = run_bg([PYTHON, f"{SCRIPTS}/train.py", "--phase", "1",
                          "--data-root", str(DATA_ROOT)],
                         DATA_ROOT / "train_phase1.log")
            print(f"Phase 1 PID: {pid}", flush=True)
            phase1_started = True

        # Start embedding after Phase 1
        proj_head = DATA_ROOT / "projection_head_a.pt"
        if proj_head.exists() and not embed_started and not is_running("embed_all"):
            print("Starting embedding...", flush=True)
            pid = run_bg([PYTHON, f"{SCRIPTS}/embed_all.py",
                          "--data-root", str(DATA_ROOT)],
                         DATA_ROOT / "embed.log")
            print(f"Embed PID: {pid}", flush=True)
            embed_started = True

        # Build index after embeddings
        if embeddings >= 900000 and not index_started and not is_running("build_index"):
            print("Building FAISS index...", flush=True)
            pid = run_bg([PYTHON, f"{SCRIPTS}/build_index.py",
                          "--data-root", str(DATA_ROOT)],
                         DATA_ROOT / "index.log")
            print(f"Index PID: {pid}", flush=True)
            index_started = True

        # Phase 2 training after index
        if index_exists and not phase2_started and not is_running("train.py"):
            print("Starting Phase 2 training...", flush=True)
            pid = run_bg([PYTHON, f"{SCRIPTS}/train.py", "--phase", "2",
                          "--data-root", str(DATA_ROOT), "--epochs", "10"],
                         DATA_ROOT / "train_phase2.log")
            print(f"Phase 2 PID: {pid}", flush=True)
            phase2_started = True

        # Start serving after Phase 2
        if sketch_enc and not serve_started and not is_running("serve.py"):
            print("Starting serving endpoint on port 8000...", flush=True)
            pid = run_bg([PYTHON, f"{SCRIPTS}/serve.py",
                          "--data-root", str(DATA_ROOT)],
                         DATA_ROOT / "serve.log")
            print(f"Serve PID: {pid}", flush=True)
            serve_started = True
            print("PIPELINE COMPLETE! Service running on port 8000.", flush=True)

        time.sleep(60)


if __name__ == "__main__":
    main()
