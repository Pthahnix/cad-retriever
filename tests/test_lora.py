import torch
from cad_retriever.models.lora import apply_lora, count_trainable_params
from cad_retriever.models.encoder import SketchEncoder


def test_lora_applies_to_sketch_encoder():
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    before = count_trainable_params(enc)
    apply_lora(enc.visual, rank=16)
    after = count_trainable_params(enc)
    # LoRA adds trainable params to frozen visual backbone
    assert after > before


def test_lora_output_unchanged_at_init():
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    x = torch.randn(1, 3, 224, 224)
    out_before = enc(x).detach().clone()
    apply_lora(enc.visual, rank=16)
    out_after = enc(x).detach()
    # At init, LoRA B is zero so output should be identical
    assert torch.allclose(out_before, out_after, atol=1e-4)


def test_lora_rank_parameter():
    enc = SketchEncoder(embed_dim=512, lora_rank=8)
    apply_lora(enc.visual, rank=8)
    # Check that LoRA layers exist with correct rank
    found = False
    for name, module in enc.visual.named_modules():
        if hasattr(module, "lora_A"):
            assert module.lora_A.shape[0] == 8
            found = True
            break
    assert found
