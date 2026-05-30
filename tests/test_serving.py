import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_app(tmp_path):
    from cad_retriever.index.build_index import build_faiss_index
    vectors = np.random.randn(100, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "cad.index"
    build_faiss_index(vectors, index_path, nlist=10)
    model_ids = [f"model_{i:06d}" for i in range(100)]
    (tmp_path / "model_ids.txt").write_text("\n".join(model_ids))

    with patch("cad_retriever.serving.app.get_config") as mock_cfg:
        from cad_retriever.config import Config
        cfg = Config(data_root=tmp_path)
        mock_cfg.return_value = cfg
        from cad_retriever.serving.app import create_app
        app = create_app(index_path=index_path, model_ids=model_ids)
        yield TestClient(app)


def test_health_endpoint(mock_app):
    resp = mock_app.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_search_endpoint_returns_results(mock_app):
    from PIL import Image
    import io
    img = Image.new("RGB", (224, 224), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = mock_app.post("/search", files={"sketch": ("test.png", buf, "image/png")},
                         data={"top_k": "5"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 5
    assert "model_id" in results[0]
    assert "score" in results[0]
