import torch
from cad_retriever.training.losses import InfoNCELoss, ViewConsistencyLoss


def test_infonce_perfect_match():
    loss_fn = InfoNCELoss(temperature=0.07)
    # Identical embeddings should give low loss
    emb = torch.randn(4, 512)
    emb = torch.nn.functional.normalize(emb, dim=-1)
    loss = loss_fn(emb, emb)
    assert loss.item() < 0.1


def test_infonce_random_gives_higher_loss():
    loss_fn = InfoNCELoss(temperature=0.07)
    a = torch.nn.functional.normalize(torch.randn(32, 512), dim=-1)
    b = torch.nn.functional.normalize(torch.randn(32, 512), dim=-1)
    loss = loss_fn(a, b)
    # Random pairs should give loss close to log(batch_size)
    assert loss.item() > 2.0


def test_view_consistency_same_views():
    loss_fn = ViewConsistencyLoss()
    # 6 identical views should give zero loss
    view_embs = torch.randn(2, 6, 512)
    view_embs = view_embs[:, :1, :].expand(-1, 6, -1)
    loss = loss_fn(view_embs)
    assert loss.item() < 1e-5


def test_infonce_gradient_flows():
    loss_fn = InfoNCELoss(temperature=0.07)
    a_raw = torch.randn(8, 512, requires_grad=True)
    a = torch.nn.functional.normalize(a_raw, dim=-1)
    b = torch.nn.functional.normalize(torch.randn(8, 512), dim=-1)
    loss = loss_fn(a, b)
    loss.backward()
    assert a_raw.grad is not None
