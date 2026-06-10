import torch
import torch.nn as nn
import torch.nn.functional as F


class InfoNCELoss(nn.Module):
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = nn.Parameter(torch.tensor(temperature))

    def forward(self, query_emb: torch.Tensor, key_emb: torch.Tensor) -> torch.Tensor:
        """Symmetric InfoNCE loss.
        query_emb: (B, D) normalized
        key_emb: (B, D) normalized
        """
        logits = query_emb @ key_emb.T / self.temperature  # (B, B)
        labels = torch.arange(logits.shape[0], device=logits.device)
        loss_q2k = F.cross_entropy(logits, labels)
        loss_k2q = F.cross_entropy(logits.T, labels)
        return (loss_q2k + loss_k2q) / 2


class ViewConsistencyLoss(nn.Module):
    def forward(self, view_embeddings: torch.Tensor) -> torch.Tensor:
        """Encourage all views of same CAD to have similar embeddings.
        view_embeddings: (B, num_views, D)
        """
        mean_emb = view_embeddings.mean(dim=1, keepdim=True)  # (B, 1, D)
        diff = view_embeddings - mean_emb  # (B, V, D)
        return (diff ** 2).mean()
