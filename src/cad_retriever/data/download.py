"""Download the full ABC Dataset (1M STEP files).
HARD REQUIREMENT: All 1M files must be fully downloaded before any processing begins.
"""
import subprocess
from pathlib import Path
from tqdm import tqdm


ABC_CHUNKS_URL = "https://archive.nyu.edu/rest/bitstreams/{chunk_id}/retrieve"
ABC_MANIFEST_URL = "https://deep-geometry.github.io/abc-dataset/data/abc_chunk_ids.txt"


def download_abc_dataset(output_dir: Path, verify: bool = True):
    """Download all ABC dataset chunks and extract STEP files.
    This downloads the COMPLETE 1M dataset. No partial downloads allowed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "chunk_ids.txt"

    # Download manifest
    subprocess.run(
        ["curl", "-o", str(manifest_path), ABC_MANIFEST_URL],
        check=True,
    )
    chunk_ids = manifest_path.read_text().strip().split("\n")
    print(f"ABC Dataset: {len(chunk_ids)} chunks to download")

    # Download each chunk
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    for chunk_id in tqdm(chunk_ids, desc="Downloading ABC chunks"):
        chunk_path = chunks_dir / f"{chunk_id}.7z"
        if chunk_path.exists():
            continue
        url = ABC_CHUNKS_URL.format(chunk_id=chunk_id)
        subprocess.run(["curl", "-o", str(chunk_path), url], check=True)

    # Extract all chunks
    step_dir = output_dir / "step"
    step_dir.mkdir(exist_ok=True)
    for chunk_file in tqdm(sorted(chunks_dir.glob("*.7z")), desc="Extracting"):
        subprocess.run(
            ["7z", "x", str(chunk_file), f"-o{step_dir}", "-y", "*.step"],
            check=True, capture_output=True,
        )

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
