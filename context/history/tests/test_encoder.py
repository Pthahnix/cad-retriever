import torch
import pytest


def test_cad_encoder_output_shape():
    from cad_retriever.models.encoder import CADEncoder
    enc = CADEncoder(embed_dim=512)
    # 6 views, batch of 2
    images = torch.randn(2, 6, 3, 224, 224)
    out = enc(images)
    assert out.shape == (2, 512)


def test_sketch_encoder_output_shape():
    from cad_retriever.models.encoder import SketchEncoder
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    images = torch.randn(2, 3, 224, 224)
    out = enc(images)
    assert out.shape == (2, 512)


def test_embeddings_are_normalized():
    from cad_retriever.models.encoder import CADEncoder
    enc = CADEncoder(embed_dim=512)
    images = torch.randn(1, 6, 3, 224, 224)
    out = enc(images)
    norm = torch.norm(out, dim=-1)
    assert torch.allclose(norm, torch.ones(1), atol=1e-5)
