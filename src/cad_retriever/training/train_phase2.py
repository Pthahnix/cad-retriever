import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import GradScaler, autocast
from tqdm import tqdm

from cad_retriever.config import Config
from cad_retriever.models.encoder import SketchEncoder
from cad_retriever.models.lora import apply_lora
from cad_retriever.training.dataset import Phase2Dataset
from cad_retriever.training.losses import InfoNCELoss


def train_phase2(config: Config, model_ids: list[str], num_epochs: int = 10):
    device = torch.device("cuda")
    encoder = SketchEncoder(embed_dim=config.embed_dim, lora_rank=config.lora_rank)
    apply_lora(encoder.visual, rank=config.lora_rank)
    encoder = encoder.to(device)

    loss_fn = InfoNCELoss(temperature=config.temperature).to(device)
    scaler = GradScaler()

    trainable = [p for p in encoder.parameters() if p.requires_grad]
    trainable += list(loss_fn.parameters())
    optimizer = AdamW(trainable, lr=config.lr_phase2)

    dataset = Phase2Dataset(
        sketches_dir=config.sketches_dir,
        embeddings_dir=config.embeddings_dir,
        model_ids=model_ids,
        num_views=config.num_views,
    )
    loader = DataLoader(dataset, batch_size=config.batch_size_phase2,
                        shuffle=True, num_workers=8, pin_memory=True,
                        drop_last=True)
    scheduler = CosineAnnealingLR(optimizer, T_max=len(loader) * num_epochs)

    for epoch in range(num_epochs):
        encoder.train()
        total_loss = 0.0
        for batch in tqdm(loader, desc=f"Phase 2 Epoch {epoch+1}"):
            sketches = batch["sketch"].to(device)
            cad_embs = batch["cad_embedding"].to(device)
            with autocast():
                sketch_embs = encoder(sketches)
                cad_embs_norm = torch.nn.functional.normalize(cad_embs, dim=-1)
                loss = loss_fn(sketch_embs, cad_embs_norm)
            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            total_loss += loss.item()
        avg_loss = total_loss / len(loader)
        print(f"Epoch {epoch+1}: loss={avg_loss:.4f}, tau={loss_fn.temperature.item():.4f}")

    torch.save(encoder.state_dict(), config.data_root / "sketch_encoder.pt")
    return encoder
