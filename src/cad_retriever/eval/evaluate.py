import numpy as np
import torch
from pathlib import Path
from tqdm import tqdm
from torch.utils.data import DataLoader

from cad_retriever.config import Config
from cad_retriever.models.encoder import SketchEncoder
from cad_retriever.models.lora import apply_lora
from cad_retriever.training.dataset import Phase2Dataset
from cad_retriever.index.build_index import load_faiss_index
from cad_retriever.index.search import search_index
from cad_retriever.eval.metrics import recall_at_k, mean_reciprocal_rank


def evaluate(config: Config, test_model_ids: list[str], all_model_ids: list[str]):
    """Run full evaluation: embed test sketches, search index, compute metrics."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load encoder
    encoder = SketchEncoder(embed_dim=config.embed_dim, lora_rank=config.lora_rank)
    apply_lora(encoder.visual, rank=config.lora_rank)
    encoder.load_state_dict(
        torch.load(config.data_root / "sketch_encoder.pt", map_location=device)
    )
    encoder = encoder.to(device).eval()

    # Load index
    faiss_index = load_faiss_index(config.index_path)

    # Build model_id → index mapping
    id_to_idx = {mid: i for i, mid in enumerate(all_model_ids)}

    # Evaluate
    dataset = Phase2Dataset(
        sketches_dir=config.sketches_dir,
        embeddings_dir=config.embeddings_dir,
        model_ids=test_model_ids,
        num_views=config.num_views,
    )
    loader = DataLoader(dataset, batch_size=64, num_workers=4, pin_memory=True)

    all_retrieved = []
    all_gt = []

    with torch.no_grad():
        for batch in tqdm(loader, desc="Evaluating"):
            sketches = batch["sketch"].to(device)
            query_embs = encoder(sketches).cpu().numpy()
            indices, _ = search_index(faiss_index, query_embs,
                                      top_k=100, nprobe=config.faiss_nprobe)
            all_retrieved.append(indices)
            batch_size = sketches.shape[0]
            start_idx = len(all_gt)
            for i in range(batch_size):
                entry_idx = start_idx + i
                mid, _ = dataset._entries[entry_idx]
                all_gt.append(id_to_idx[mid])

    retrieved = np.concatenate(all_retrieved, axis=0)
    ground_truth = np.array(all_gt)

    results = {
        "recall@1": recall_at_k(retrieved, ground_truth, k=1),
        "recall@5": recall_at_k(retrieved, ground_truth, k=5),
        "recall@10": recall_at_k(retrieved, ground_truth, k=10),
        "mrr": mean_reciprocal_rank(retrieved, ground_truth),
        "num_queries": len(ground_truth),
    }
    return results
