import numpy as np
import faiss
from pathlib import Path
from cad_retriever.index.build_index import build_faiss_index, load_faiss_index


def test_build_index_creates_file(tmp_path):
    vectors = np.random.randn(1000, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=32)
    assert index_path.exists()


def test_build_index_correct_size(tmp_path):
    vectors = np.random.randn(1000, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=32)
    index = load_faiss_index(index_path)
    assert index.ntotal == 1000
