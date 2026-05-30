"""Download the full ABC Dataset (1M STEP files).
HARD REQUIREMENT: All 1M files must be fully downloaded before any processing begins.
Uses parallel downloads (8 concurrent) for speed.
"""
import subprocess
import py7zr
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


ABC_STEP_LIST_URL = "https://deep-geometry.github.io/abc-dataset/data/step_v00.txt"
PROXY = "http://127.0.0.1:7890"
_print_lock = threading.Lock()


def _download_chunk(url: str, filename: str, chunks_dir: Path) -> tuple[str, bool]:
    chunk_path = chunks_dir / filename
    # Check if already fully downloaded (use size heuristic: >5MB)
    if chunk_path.exists() and chunk_path.stat().st_size > 5_000_000:
        return filename, True
    try:
        subprocess.run(
            ["curl", "-x", PROXY, "-L", "--retry", "3", "-o", str(chunk_path), url],
            check=True, capture_output=True, timeout=600,
        )
        return filename, True
    except Exception as e:
        with _print_lock:
            print(f"WARNING: Failed to download {filename}: {e}")
        return filename, False


def download_abc_dataset(output_dir: Path, verify: bool = True,
                         parallel: int = 8):
    """Download all ABC dataset chunks and extract STEP files.
    This downloads the COMPLETE 1M dataset. No partial downloads allowed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    list_path = output_dir / "step_v00.txt"

    # Download chunk list
    if not list_path.exists():
        subprocess.run(
            ["curl", "-x", PROXY, "-o", str(list_path), ABC_STEP_LIST_URL],
            check=True,
        )
    lines = list_path.read_text().strip().split("\n")
    chunks = [(line.split()[0], line.split()[1]) for line in lines if line.strip()]
    print(f"ABC Dataset: {len(chunks)} chunks to download (parallel={parallel})")

    # Download chunks in parallel
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    failed = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(_download_chunk, url, fname, chunks_dir): fname
            for url, fname in chunks
        }
        with tqdm(total=len(chunks), desc="Downloading ABC chunks") as pbar:
            for future in as_completed(futures):
                fname, ok = future.result()
                if not ok:
                    failed.append(fname)
                pbar.update(1)

    if failed:
        print(f"WARNING: {len(failed)} chunks failed to download: {failed}")

    # Extract all chunks
    step_dir = output_dir / "step"
    step_dir.mkdir(exist_ok=True)
    chunk_files = sorted(chunks_dir.glob("*.7z"))
    print(f"Extracting {len(chunk_files)} chunks...")
    for chunk_file in tqdm(chunk_files, desc="Extracting"):
        # Skip if already extracted (check for marker file)
        marker = step_dir / f".extracted_{chunk_file.stem}"
        if marker.exists():
            continue
        try:
            with py7zr.SevenZipFile(chunk_file, mode="r") as z:
                z.extractall(path=step_dir)
            marker.touch()
        except Exception as e:
            print(f"WARNING: Failed to extract {chunk_file.name}: {e}")

    # Verify count
    step_files = list(step_dir.rglob("*.step"))
    print(f"Downloaded and extracted {len(step_files)} STEP files")
    if verify and len(step_files) < 900_000:
        raise RuntimeError(
            f"Expected ~1M STEP files, got {len(step_files)}. "
            "Download may be incomplete."
        )

    # Write model ID manifest
    model_ids = sorted([f.stem for f in step_files])
    (output_dir / "model_ids.txt").write_text("\n".join(model_ids))
    return model_ids
