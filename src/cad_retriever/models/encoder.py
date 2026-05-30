import torch
import torch.nn as nn
import open_clip


class ProjectionHead(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.linear = nn.Linear(in_dim, out_dim)
        self.norm = nn.LayerNorm(out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.norm(self.linear(x))


class CADEncoder(nn.Module):
    def __init__(self, embed_dim: int = 512, clip_model: str = "ViT-B-16",
                 pretrained: str = "laion2b_s34b_b88k"):
        super().__init__()
        model, _, self.preprocess = open_clip.create_model_and_transforms(
            clip_model, pretrained=pretrained
        )
        self.visual = model.visual
        for param in self.visual.parameters():
            param.requires_grad = False
        clip_out_dim = getattr(self.visual, "output_dim", 512)
        self.projection = ProjectionHead(clip_out_dim, embed_dim)

    def encode_single_view(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self.visual(x)

    def forward(self, views: torch.Tensor) -> torch.Tensor:
        """views: (B, num_views, 3, H, W)"""
        B, V, C, H, W = views.shape
        flat = views.reshape(B * V, C, H, W)
        feats = self.encode_single_view(flat)  # (B*V, 768)
        feats = feats.reshape(B, V, -1).mean(dim=1)  # (B, 768)
        out = self.projection(feats)  # (B, 512)
        return nn.functional.normalize(out, dim=-1)


class SketchEncoder(nn.Module):
    def __init__(self, embed_dim: int = 512, lora_rank: int = 16,
                 clip_model: str = "ViT-B-16",
                 pretrained: str = "laion2b_s34b_b88k"):
        super().__init__()
        model, _, self.preprocess = open_clip.create_model_and_transforms(
            clip_model, pretrained=pretrained
        )
        self.visual = model.visual
        for param in self.visual.parameters():
            param.requires_grad = False
        clip_out_dim = getattr(self.visual, "output_dim", 512)
        self.projection = ProjectionHead(clip_out_dim, embed_dim)
        self.lora_rank = lora_rank
        # LoRA will be applied in Task 3

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 3, H, W)"""
        with torch.no_grad():
            feats = self.visual(x)  # (B, 768)
        out = self.projection(feats)  # (B, 512)
        return nn.functional.normalize(out, dim=-1)
