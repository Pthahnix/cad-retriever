import numpy as np
import faiss
from pathlib import Path


def mine_hard_negatives(
    embeddings_dir: Path,
    model_ids: list[str],
    top_k: int = 50,
    hard_range: tuple[int, int] = (5, 20),
) -> dict[str, list[str]]:
    """For each model, find hard negatives (rank 5-20 in current embedding space)."""
    vectors = []
    for mid in model_ids:
        vec = np.load(embeddings_dir / f"{mid}.npy")
        vectors.append(vec)
    vectors = np.stack(vectors).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    d = vectors.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(vectors)
    _, indices = index.search(vectors, top_k)

    hard_negs = {}
    lo, hi = hard_range
    for i, mid in enumerate(model_ids):
        neg_indices = indices[i, lo:hi]
        hard_negs[mid] = [model_ids[j] for j in neg_indices]
    return hard_negs
