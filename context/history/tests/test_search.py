import numpy as np
from cad_retriever.index.search import search_index
from cad_retriever.index.build_index import build_faiss_index, load_faiss_index


def test_search_finds_exact_match(tmp_path):
    vectors = np.random.randn(100, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=10)
    index = load_faiss_index(index_path)
    # Search for the first vector — should find itself
    query = vectors[0:1]
    indices, scores = search_index(index, query, top_k=5, nprobe=10)
    assert indices[0][0] == 0
    assert scores[0][0] > 0.99


def test_search_returns_correct_shape(tmp_path):
    vectors = np.random.randn(100, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=10)
    index = load_faiss_index(index_path)
    query = np.random.randn(3, 512).astype(np.float32)
    query = query / np.linalg.norm(query, axis=1, keepdims=True)
    indices, scores = search_index(index, query, top_k=10, nprobe=10)
    assert indices.shape == (3, 10)
    assert scores.shape == (3, 10)
