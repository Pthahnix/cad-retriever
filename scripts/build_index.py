"""Build FAISS index from all precomputed CAD embeddings."""
import argparse
import numpy as np
from pathlib import Path
from tqdm import tqdm
from cad_retriever.config import Config
from cad_retriever.index.build_index import build_faiss_index

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
args = parser.parse_args()

config = Config(data_root=args.data_root)
model_ids = (config.data_root / "model_ids.txt").read_text().strip().split("\n")

print(f"Loading {len(model_ids)} embeddings...")
vectors = []
for mid in tqdm(model_ids):
    vec = np.load(config.embeddings_dir / f"{mid}.npy")
    vectors.append(vec)
vectors = np.stack(vectors).astype(np.float32)

print(f"Building FAISS index ({vectors.shape})...")
build_faiss_index(vectors, config.index_path, nlist=config.faiss_nlist)
print(f"Index saved to {config.index_path}")
