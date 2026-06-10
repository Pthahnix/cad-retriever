import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import GradScaler, autocast
from tqdm import tqdm

from cad_retriever.config import Config
from cad_retriever.models.encoder import CADEncoder
from cad_retriever.training.dataset import Phase1ContrastiveDataset
from cad_retriever.training.losses import InfoNCELoss


def train_phase1(config: Config, model_ids: list[str],
                 num_epochs: int = 5, lr: float = 1e-3,
                 batch_size: int = 256):
    device = torch.device("cuda")
    encoder = CADEncoder(embed_dim=config.embed_dim).to(device)
    loss_fn = InfoNCELoss(temperature=config.temperature).to(device)
    scaler = GradScaler()

    trainable = list(encoder.projection.parameters()) + list(loss_fn.parameters())
    optimizer = AdamW(trainable, lr=lr)

    dataset = Phase1ContrastiveDataset(
        renders_dir=config.renders_dir,
        model_ids=model_ids,
        num_views=config.num_views,
    )
    loader = DataLoader(dataset, batch_size=batch_size,
                        shuffle=True, num_workers=8, pin_memory=True,
                        drop_last=True, persistent_workers=True)
    scheduler = CosineAnnealingLR(optimizer, T_max=len(loader) * num_epochs)

    encoder.train()
    for epoch in range(num_epochs):
        total_loss = 0.0
        for batch in tqdm(loader, desc=f"Phase 1 Epoch {epoch+1}/{num_epochs}"):
            views_a = batch["view_a"].to(device)
            views_b = batch["view_b"].to(device)

            with torch.no_grad():
                feats_a = encoder.encode_single_view(views_a)
                feats_b = encoder.encode_single_view(views_b)

            with autocast():
                emb_a = encoder.projection(feats_a)
                emb_a = torch.nn.functional.normalize(emb_a, dim=-1)
                emb_b = encoder.projection(feats_b)
                emb_b = torch.nn.functional.normalize(emb_b, dim=-1)
                loss = loss_fn(emb_a, emb_b)

            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            total_loss += loss.item()

        avg = total_loss / len(loader)
        print(f"Epoch {epoch+1}: loss={avg:.4f}, tau={loss_fn.temperature.item():.4f}")

    torch.save(encoder.projection.state_dict(),
               config.data_root / "projection_head_a.pt")
    return encoder
