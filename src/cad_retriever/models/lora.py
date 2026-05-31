import torch
import torch.nn as nn
import math


class LoRALinear(nn.Module):
    def __init__(self, original: nn.Linear, rank: int):
        super().__init__()
        self.original = original
        self.original.weight.requires_grad = False
        if self.original.bias is not None:
            self.original.bias.requires_grad = False
        in_features = original.in_features
        out_features = original.out_features
        self.in_features = in_features
        self.out_features = out_features
        self.lora_A = nn.Parameter(torch.zeros(rank, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        # B initialized to zero so LoRA is identity at start

    @property
    def weight(self):
        # Return combined weight so PyTorch MHA's F.multi_head_attention_forward
        # picks up LoRA parameters in the computation graph.
        return self.original.weight + self.lora_B @ self.lora_A

    @property
    def bias(self):
        return self.original.bias

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return nn.functional.linear(x, self.weight, self.bias)


def apply_lora(model: nn.Module, rank: int, target_modules: tuple = ("out_proj",)):
    for name, module in list(model.named_modules()):
        for target in target_modules:
            if target in name and isinstance(module, nn.Linear):
                parts = name.split(".")
                parent = model
                for part in parts[:-1]:
                    parent = getattr(parent, part)
                setattr(parent, parts[-1], LoRALinear(module, rank))


def count_trainable_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
