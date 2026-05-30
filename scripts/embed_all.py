"""Compute CAD embeddings for all 1M models using Phase 1 encoder."""
import argparse
import torch
import numpy as np
from pathlib import Path
from tqdm import tqdm
from cad_retriever.config import Config
from cad_retriever.models.encoder import CADEncoder
from cad_retriever.training.dataset import Phase1Dataset
from torch.utils.data import DataLoader

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
parser.add_argument("--batch-size", type=int, default=128)
args = parser.parse_args()

config = Config(data_root=args.data_root)
device = torch.device("cuda")

encoder = CADEncoder(embed_dim=config.embed_dim).to(device)
encoder.projection.load_state_dict(
    torch.load(config.data_root / "projection_head_a.pt", map_location=device)
)
encoder.eval()

model_ids = (config.data_root / "model_ids.txt").read_text().strip().split("\n")
dataset = Phase1Dataset(config.renders_dir, model_ids, config.num_views)
loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=8, pin_memory=True)

config.embeddings_dir.mkdir(parents=True, exist_ok=True)
with torch.no_grad():
    for batch in tqdm(loader, desc="Computing embeddings"):
        views = batch["views"].to(device)
        embs = encoder(views).cpu().numpy()
        for mid, emb in zip(batch["model_id"], embs):
            np.save(config.embeddings_dir / f"{mid}.npy", emb)
