#!/usr/bin/env python3
"""
Monitor download progress and automatically start the next pipeline step.
"""
import time
import subprocess
import sys
from pathlib import Path

DATA_ROOT = Path("/home/cc/data")
CHUNKS_DIR = DATA_ROOT / "abc_step" / "chunks"
STEP_DIR = DATA_ROOT / "abc_step" / "step"
PIPELINE_LOG = DATA_ROOT / "pipeline.log"
PYTHON = "/root/miniconda3/bin/python3"
SCRIPTS = "/home/cc/cad-retriever/scripts"


def is_download_running():
    result = subprocess.run(
        ["pgrep", "-f", "download_abc.py"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def main():
    print("Monitoring download progress...", flush=True)
    while True:
        chunks = len(list(CHUNKS_DIR.glob("*.7z"))) if CHUNKS_DIR.exists() else 0
        step_files = len(list(STEP_DIR.rglob("*.step"))) if STEP_DIR.exists() else 0
        running = is_download_running()

        msg = (f"[{time.strftime('%H:%M:%S')}] Chunks: {chunks}/100 | "
               f"STEP files: {step_files} | Download running: {running}")
        print(msg, flush=True)

        if not running and chunks >= 90:
            print("Download appears complete! Checking STEP files...", flush=True)
            if step_files >= 900_000:
                print(f"SUCCESS: {step_files} STEP files. Starting pipeline...", flush=True)
                with open(PIPELINE_LOG, "w") as log:
                    subprocess.Popen(
                        [PYTHON, f"{SCRIPTS}/run_pipeline.py",
                         "--skip-download", "--data-root", str(DATA_ROOT)],
                        stdout=log, stderr=subprocess.STDOUT,
                        cwd="/home/cc/cad-retriever",
                    )
                print(f"Pipeline started. Log: {PIPELINE_LOG}", flush=True)
                break
            else:
                print(f"Only {step_files} STEP files. Waiting...", flush=True)

        time.sleep(60)


if __name__ == "__main__":
    main()
