import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from pathlib import Path
import numpy as np
from tqdm import tqdm

from cad_retriever.config import Config
from cad_retriever.models.encoder import CADEncoder
from cad_retriever.training.dataset import Phase1Dataset
from cad_retriever.training.losses import ViewConsistencyLoss


def train_phase1(config: Config, model_ids: list[str]):
    device = torch.device("cuda")
    encoder = CADEncoder(embed_dim=config.embed_dim).to(device)
    loss_fn = ViewConsistencyLoss()
    optimizer = AdamW(encoder.projection.parameters(), lr=config.lr_phase1)

    dataset = Phase1Dataset(
        renders_dir=config.renders_dir,
        model_ids=model_ids,
        num_views=config.num_views,
    )
    loader = DataLoader(dataset, batch_size=config.batch_size_phase1,
                        shuffle=True, num_workers=8, pin_memory=True)
    scheduler = CosineAnnealingLR(optimizer, T_max=len(loader))

    encoder.train()
    for batch in tqdm(loader, desc="Phase 1"):
        views = batch["views"].to(device)  # (B, 6, 3, 224, 224)
        B, V, C, H, W = views.shape
        flat = views.reshape(B * V, C, H, W)
        with torch.no_grad():
            feats = encoder.encode_single_view(flat)  # (B*V, clip_dim)
        feats = feats.reshape(B, V, -1)
        projected = encoder.projection(feats.reshape(B * V, -1))
        projected = projected.reshape(B, V, -1)
        loss = loss_fn(projected)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        scheduler.step()

    # Save projection head
    torch.save(encoder.projection.state_dict(),
               config.data_root / "projection_head_a.pt")
    return encoder
