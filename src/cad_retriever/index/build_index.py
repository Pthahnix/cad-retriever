import numpy as np
import faiss
from pathlib import Path


def build_faiss_index(vectors: np.ndarray, index_path: Path, nlist: int = 1024):
    """Build and save a FAISS IVFFlat index with inner product metric.
    Uses GPU for training if available, then moves to CPU for storage.
    """
    d = vectors.shape[1]
    quantizer = faiss.IndexFlatIP(d)
    index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_INNER_PRODUCT)

    # Use GPU for training if available
    try:
        res = faiss.StandardGpuResources()
        gpu_index = faiss.index_cpu_to_gpu(res, 0, index)
        gpu_index.train(vectors)
        gpu_index.add(vectors)
        index = faiss.index_gpu_to_cpu(gpu_index)
    except Exception:
        # Fallback to CPU
        index.train(vectors)
        index.add(vectors)

    faiss.write_index(index, str(index_path))


def load_faiss_index(index_path: Path) -> faiss.Index:
    """Load a FAISS index from disk."""
    return faiss.read_index(str(index_path))
