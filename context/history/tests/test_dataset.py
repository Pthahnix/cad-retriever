import torch
import numpy as np
from pathlib import Path
from PIL import Image
from cad_retriever.training.dataset import Phase1Dataset, Phase2Dataset


def _create_mock_data(tmp_path: Path, num_models: int = 5, num_views: int = 6):
    renders_dir = tmp_path / "renders"
    edges_dir = tmp_path / "edges"
    sketches_dir = tmp_path / "sketches"
    for d in [renders_dir, edges_dir, sketches_dir]:
        d.mkdir(parents=True)
    model_ids = []
    for i in range(num_models):
        mid = f"model_{i:06d}"
        model_ids.append(mid)
        (renders_dir / mid).mkdir()
        (edges_dir / mid).mkdir()
        (sketches_dir / mid).mkdir()
        for v in range(num_views):
            img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
            img.save(renders_dir / mid / f"view_{v}.png")
            edge = Image.fromarray(np.random.randint(0, 255, (224, 224), dtype=np.uint8))
            edge.save(edges_dir / mid / f"view_{v}.png")
            edge.save(sketches_dir / mid / f"view_{v}.png")
    return model_ids


def test_phase1_dataset_returns_views(tmp_path):
    model_ids = _create_mock_data(tmp_path)
    ds = Phase1Dataset(renders_dir=tmp_path / "renders", model_ids=model_ids, num_views=6)
    item = ds[0]
    assert item["views"].shape == (6, 3, 224, 224)
    assert item["model_id"] == model_ids[0]


def test_phase2_dataset_returns_sketch_and_embedding(tmp_path):
    model_ids = _create_mock_data(tmp_path)
    # Create fake precomputed embeddings
    emb_dir = tmp_path / "embeddings"
    emb_dir.mkdir()
    for mid in model_ids:
        np.save(emb_dir / f"{mid}.npy", np.random.randn(512).astype(np.float32))
    ds = Phase2Dataset(
        sketches_dir=tmp_path / "sketches",
        embeddings_dir=emb_dir,
        model_ids=model_ids,
        num_views=6,
    )
    item = ds[0]
    assert item["sketch"].shape == (3, 224, 224)
    assert item["cad_embedding"].shape == (512,)
