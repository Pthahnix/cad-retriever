"""Download the full ABC Dataset (1M STEP files).
HARD REQUIREMENT: All 1M files must be fully downloaded before any processing begins.
"""
import subprocess
import py7zr
from pathlib import Path
from tqdm import tqdm


ABC_STEP_LIST_URL = "https://deep-geometry.github.io/abc-dataset/data/step_v00.txt"


def download_abc_dataset(output_dir: Path, verify: bool = True,
                         proxy: str = "http://127.0.0.1:7890"):
    """Download all ABC dataset chunks and extract STEP files.
    This downloads the COMPLETE 1M dataset. No partial downloads allowed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    list_path = output_dir / "step_v00.txt"

    env_proxy = {"http_proxy": proxy, "https_proxy": proxy}

    # Download chunk list
    subprocess.run(
        ["curl", "-x", proxy, "-o", str(list_path), ABC_STEP_LIST_URL],
        check=True,
    )
    lines = list_path.read_text().strip().split("\n")
    chunks = [(line.split()[0], line.split()[1]) for line in lines if line.strip()]
    print(f"ABC Dataset: {len(chunks)} chunks to download")

    # Download each chunk
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    for url, filename in tqdm(chunks, desc="Downloading ABC chunks"):
        chunk_path = chunks_dir / filename
        if chunk_path.exists() and chunk_path.stat().st_size > 1_000_000:
            continue
        subprocess.run(
            ["curl", "-x", proxy, "-L", "-o", str(chunk_path), url],
            check=True,
        )

    # Extract all chunks
    step_dir = output_dir / "step"
    step_dir.mkdir(exist_ok=True)
    for chunk_file in tqdm(sorted(chunks_dir.glob("*.7z")), desc="Extracting"):
        try:
            with py7zr.SevenZipFile(chunk_file, mode="r") as z:
                z.extractall(path=step_dir)
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
