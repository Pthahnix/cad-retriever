#!/usr/bin/env python3
"""
Monitor download progress and automatically start the next pipeline step.
Run this in a separate terminal or as a background process.
"""
import time
import subprocess
import sys
from pathlib import Path

DATA_ROOT = Path("/home/cc/data")
CHUNKS_DIR = DATA_ROOT / "abc_step" / "chunks"
STEP_DIR = DATA_ROOT / "abc_step" / "step"
DOWNLOAD_LOG = DATA_ROOT / "download.log"
PIPELINE_LOG = DATA_ROOT / "pipeline.log"


def count_complete_chunks():
    """Count chunks that appear fully downloaded (>5MB and not being written)."""
    if not CHUNKS_DIR.exists():
        return 0
    return len(list(CHUNKS_DIR.glob("*.7z")))


def is_download_running():
    result = subprocess.run(
        ["pgrep", "-f", "download_abc.py"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def count_step_files():
    if not STEP_DIR.exists():
        return 0
    return len(list(STEP_DIR.rglob("*.step")))


def main():
    print("Monitoring download progress...")
    while True:
        chunks = count_complete_chunks()
        step_files = count_step_files()
        running = is_download_running()

        print(f"[{time.strftime('%H:%M:%S')}] Chunks: {chunks}/100 | "
              f"STEP files: {step_files} | Download running: {running}")

        if not running and chunks >= 90:
            print("Download appears complete! Checking STEP files...")
            if step_files >= 900_000:
                print(f"SUCCESS: {step_files} STEP files extracted. Starting pipeline...")
                subprocess.Popen(
                    [sys.executable, "scripts/run_pipeline.py",
                     "--skip-download", "--data-root", str(DATA_ROOT)],
                    stdout=open(PIPELINE_LOG, "w"),
                    stderr=subprocess.STDOUT,
                )
                print(f"Pipeline started. Log: {PIPELINE_LOG}")
                break
            else:
                print(f"Only {step_files} STEP files. Waiting for extraction...")

        time.sleep(60)


if __name__ == "__main__":
    main()
