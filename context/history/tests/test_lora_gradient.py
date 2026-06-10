import torch
from cad_retriever.models.encoder import SketchEncoder
from cad_retriever.models.lora import apply_lora


def test_lora_receives_gradients():
    """LoRA parameters must receive gradients during forward+backward."""
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    apply_lora(enc.visual, rank=16)

    x = torch.randn(2, 3, 224, 224)
    out = enc(x)
    loss = out.sum()
    loss.backward()

    found_grad = False
    for name, param in enc.named_parameters():
        if "lora_A" in name or "lora_B" in name:
            if param.grad is not None and param.grad.abs().sum() > 0:
                found_grad = True
                break
    assert found_grad, "No LoRA parameter received a gradient"
