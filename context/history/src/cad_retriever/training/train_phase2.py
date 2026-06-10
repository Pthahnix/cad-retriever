import torch
from torch.utils.data import DataLoader, random_split
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

    full_dataset = Phase2Dataset(
        sketches_dir=config.sketches_dir,
        embeddings_dir=config.embeddings_dir,
        model_ids=model_ids,
        num_views=config.num_views,
    )

    val_size = max(1, int(len(full_dataset) * 0.05))
    train_size = len(full_dataset) - val_size
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=128,
                              shuffle=True, num_workers=8, pin_memory=True,
                              drop_last=True, persistent_workers=True)
    val_loader = DataLoader(val_ds, batch_size=128,
                            num_workers=4, pin_memory=True)

    scheduler = CosineAnnealingLR(optimizer, T_max=len(train_loader) * num_epochs)
    best_val_loss = float("inf")

    for epoch in range(num_epochs):
        encoder.train()
        total_loss = 0.0
        for batch in tqdm(train_loader, desc=f"Phase 2 Epoch {epoch+1}"):
            sketches = batch["sketch"].to(device)
            cad_embs = batch["cad_embedding"].to(device)
            with autocast():
                sketch_embs = encoder(sketches)
                cad_embs_norm = torch.nn.functional.normalize(cad_embs, dim=-1)
                loss = loss_fn(sketch_embs, cad_embs_norm)
            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable, max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            total_loss += loss.item()

        avg_train = total_loss / len(train_loader)

        encoder.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                sketches = batch["sketch"].to(device)
                cad_embs = batch["cad_embedding"].to(device)
                sketch_embs = encoder(sketches)
                cad_embs_norm = torch.nn.functional.normalize(cad_embs, dim=-1)
                loss = loss_fn(sketch_embs, cad_embs_norm)
                val_loss += loss.item()
        avg_val = val_loss / len(val_loader)

        print(f"Epoch {epoch+1}: train_loss={avg_train:.4f}, "
              f"val_loss={avg_val:.4f}, tau={loss_fn.temperature.item():.4f}")

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            torch.save(encoder.state_dict(), config.data_root / "sketch_encoder.pt")
            print(f"  → Saved best checkpoint (val_loss={avg_val:.4f})")

    return encoder
