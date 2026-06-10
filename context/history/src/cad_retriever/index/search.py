import numpy as np
import faiss


def search_index(
    index: faiss.Index,
    query: np.ndarray,
    top_k: int = 100,
    nprobe: int = 64,
) -> tuple[np.ndarray, np.ndarray]:
    """Search FAISS index. Returns (indices, scores) both shape (n_queries, top_k)."""
    index.nprobe = nprobe
    scores, indices = index.search(query, top_k)
    return indices, scores
