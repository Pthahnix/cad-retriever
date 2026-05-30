import numpy as np
import faiss
from pathlib import Path


def build_faiss_index(vectors: np.ndarray, index_path: Path, nlist: int = 1024):
    """Build and save a FAISS IVFFlat index with inner product metric."""
    d = vectors.shape[1]
    quantizer = faiss.IndexFlatIP(d)
    index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_INNER_PRODUCT)
    index.train(vectors)
    index.add(vectors)
    faiss.write_index(index, str(index_path))


def load_faiss_index(index_path: Path) -> faiss.Index:
    """Load a FAISS index from disk."""
    return faiss.read_index(str(index_path))
