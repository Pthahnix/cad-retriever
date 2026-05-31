import torch
import numpy as np
from pathlib import Path
from PIL import Image


def _make_renders(tmp_path, n_models=10, n_views=6):
    renders_dir = tmp_path / "renders"
    model_ids = []
    for i in range(n_models):
        mid = f"model_{i:06d}"
        model_ids.append(mid)
        d = renders_dir / mid
        d.mkdir(parents=True)
        for v in range(n_views):
            img = Image.fromarray(
                np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
            img.save(d / f"view_{v}.png")
    return renders_dir, model_ids


def test_contrastive_dataset_returns_two_views(tmp_path):
    from cad_retriever.training.dataset import Phase1ContrastiveDataset
    renders_dir, model_ids = _make_renders(tmp_path)
    ds = Phase1ContrastiveDataset(renders_dir, model_ids, num_views=6)
    item = ds[0]
    assert item["view_a"].shape == (3, 224, 224)
    assert item["view_b"].shape == (3, 224, 224)
    assert item["model_id"] == model_ids[0]


def test_infonce_phase1_loss_decreases():
    """One training step should reduce loss."""
    from cad_retriever.models.encoder import CADEncoder
    from cad_retriever.training.losses import InfoNCELoss

    encoder = CADEncoder(embed_dim=512)
    loss_fn = InfoNCELoss(temperature=0.07)
    optimizer = torch.optim.Adam(encoder.projection.parameters(), lr=1e-3)

    views_a = torch.randn(8, 3, 224, 224)
    views_b = torch.randn(8, 3, 224, 224)

    encoder.train()
    with torch.no_grad():
        feats_a = encoder.encode_single_view(views_a)
        feats_b = encoder.encode_single_view(views_b)

    emb_a = encoder.projection(feats_a)
    emb_a = torch.nn.functional.normalize(emb_a, dim=-1)
    emb_b = encoder.projection(feats_b)
    emb_b = torch.nn.functional.normalize(emb_b, dim=-1)

    loss1 = loss_fn(emb_a, emb_b)
    optimizer.zero_grad()
    loss1.backward()
    optimizer.step()

    emb_a2 = encoder.projection(feats_a)
    emb_a2 = torch.nn.functional.normalize(emb_a2, dim=-1)
    emb_b2 = encoder.projection(feats_b)
    emb_b2 = torch.nn.functional.normalize(emb_b2, dim=-1)
    loss2 = loss_fn(emb_a2, emb_b2)

    assert loss2.item() < loss1.item()
