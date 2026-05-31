import json
import numpy as np
import faiss
from pathlib import Path
from tqdm import tqdm


def mine_hard_negatives(
    embeddings_dir: Path,
    model_ids: list[str],
    output_path: Path,
    top_k: int = 20,
    hard_range: tuple[int, int] = (5, 20),
) -> dict[str, list[str]]:
    """Mine hard negatives: for each model, find rank 5-20 nearest neighbors."""
    vectors = []
    valid_ids = []
    for mid in tqdm(model_ids, desc="Loading embeddings"):
        path = embeddings_dir / f"{mid}.npy"
        if path.exists():
            vectors.append(np.load(path))
            valid_ids.append(mid)

    vectors = np.stack(vectors).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    d = vectors.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(vectors)
    _, indices = index.search(vectors, top_k)

    lo, hi = hard_range
    hard_negs = {}
    for i, mid in enumerate(valid_ids):
        neg_indices = indices[i, lo:hi]
        hard_negs[mid] = [valid_ids[j] for j in neg_indices if j != i]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(hard_negs, f)

    print(f"Mined hard negatives for {len(hard_negs)} models → {output_path}")
    return hard_negs
