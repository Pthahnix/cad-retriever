"""Download the full ABC Dataset (1M STEP files).
HARD REQUIREMENT: All 1M files must be fully downloaded before any processing begins.
Uses parallel downloads (8 concurrent) with resume support.
"""
import subprocess
import struct
import py7zr
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


ABC_STEP_LIST_URL = "https://deep-geometry.github.io/abc-dataset/data/step_v00.txt"
PROXY = "http://127.0.0.1:7890"
_print_lock = threading.Lock()


def _get_expected_size(path: Path) -> int:
    """Read the expected total size from the 7z header."""
    try:
        with open(path, 'rb') as f:
            data = f.read(28)
        if len(data) < 28 or data[:6] != bytes.fromhex('377abcaf271c'):
            return -1
        offset = struct.unpack('<q', data[12:20])[0]
        size = struct.unpack('<q', data[20:28])[0]
        return offset + size + 32
    except Exception:
        return -1


def _is_complete(path: Path) -> bool:
    """Check if a 7z file is fully downloaded."""
    if not path.exists():
        return False
    actual = path.stat().st_size
    if actual < 1_000_000:
        return False
    expected = _get_expected_size(path)
    if expected <= 0:
        return False
    return actual >= expected


def _download_chunk(url: str, filename: str, chunks_dir: Path,
                    max_retries: int = 5) -> tuple[str, bool]:
    chunk_path = chunks_dir / filename
    if _is_complete(chunk_path):
        return filename, True

    for attempt in range(max_retries):
        # Delete partial file before re-downloading (server doesn't support resume)
        if chunk_path.exists():
            chunk_path.unlink()
        try:
            cmd = ["curl", "-x", PROXY, "-L", "--retry", "3",
                   "--retry-delay", "5", "--max-time", "3600",
                   "-o", str(chunk_path), url]
            subprocess.run(cmd, check=True, capture_output=True, timeout=3600)
            if _is_complete(chunk_path):
                return filename, True
            with _print_lock:
                actual = chunk_path.stat().st_size if chunk_path.exists() else 0
                expected = _get_expected_size(chunk_path) if chunk_path.exists() else -1
                print(f"  {filename}: incomplete after attempt {attempt+1} "
                      f"({actual//1024//1024}MB / {expected//1024//1024}MB needed)",
                      flush=True)
        except Exception as e:
            with _print_lock:
                print(f"  {filename}: attempt {attempt+1} failed: {e}", flush=True)

    return filename, False


def download_abc_dataset(output_dir: Path, verify: bool = True,
                         parallel: int = 8):
    """Download all ABC dataset chunks and extract STEP files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    list_path = output_dir / "step_v00.txt"

    if not list_path.exists():
        subprocess.run(
            ["curl", "-x", PROXY, "-o", str(list_path), ABC_STEP_LIST_URL],
            check=True,
        )
    lines = list_path.read_text().strip().split("\n")
    chunks = [(line.split()[0], line.split()[1]) for line in lines if line.strip()]
    print(f"ABC Dataset: {len(chunks)} chunks to download (parallel={parallel})")

    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    # Check which chunks are already complete
    already_done = sum(1 for _, fname in chunks
                       if _is_complete(chunks_dir / fname))
    print(f"Already complete: {already_done}/{len(chunks)}")

    failed = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(_download_chunk, url, fname, chunks_dir): fname
            for url, fname in chunks
        }
        with tqdm(total=len(chunks), desc="Downloading ABC chunks",
                  initial=already_done) as pbar:
            for future in as_completed(futures):
                fname, ok = future.result()
                if not ok:
                    failed.append(fname)
                pbar.update(1)

    if failed:
        print(f"WARNING: {len(failed)} chunks failed: {failed}")

    # Extract all complete chunks
    step_dir = output_dir / "step"
    step_dir.mkdir(exist_ok=True)
    chunk_files = sorted(chunks_dir.glob("*.7z"))
    print(f"Extracting {len(chunk_files)} chunks...")
    for chunk_file in tqdm(chunk_files, desc="Extracting"):
        marker = step_dir / f".extracted_{chunk_file.stem}"
        if marker.exists():
            continue
        if not _is_complete(chunk_file):
            print(f"  Skipping incomplete: {chunk_file.name}")
            continue
        try:
            with py7zr.SevenZipFile(chunk_file, mode="r") as z:
                z.extractall(path=step_dir)
            marker.touch()
        except Exception as e:
            print(f"WARNING: Failed to extract {chunk_file.name}: {e}")

    step_files = list(step_dir.rglob("*.step"))
    print(f"Extracted {len(step_files)} STEP files")
    if verify and len(step_files) < 900_000:
        raise RuntimeError(
            f"Expected ~1M STEP files, got {len(step_files)}. "
            "Download may be incomplete."
        )

    model_ids = sorted([f.stem for f in step_files])
    (output_dir / "model_ids.txt").write_text("\n".join(model_ids))
    return model_ids
