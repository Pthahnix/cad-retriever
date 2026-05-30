import io
import numpy as np
import torch
from pathlib import Path
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel

from cad_retriever.config import Config
from cad_retriever.models.encoder import SketchEncoder
from cad_retriever.models.lora import apply_lora
from cad_retriever.index.build_index import load_faiss_index
from cad_retriever.index.search import search_index
from cad_retriever.training.dataset import TRANSFORM


class SearchResult(BaseModel):
    model_id: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def create_app(
    index_path: Path | None = None,
    model_ids: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(title="CAD Sketch Retriever")
    config = get_config()

    # Load index
    idx_path = index_path or config.index_path
    faiss_index = load_faiss_index(idx_path)

    # Load model IDs
    if model_ids is None:
        model_ids = (config.data_root / "model_ids.txt").read_text().strip().split("\n")

    # Load sketch encoder
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    encoder = SketchEncoder(embed_dim=config.embed_dim, lora_rank=config.lora_rank)
    apply_lora(encoder.visual, rank=config.lora_rank)
    weights_path = config.data_root / "sketch_encoder.pt"
    if weights_path.exists():
        encoder.load_state_dict(torch.load(weights_path, map_location=device))
    encoder = encoder.to(device).eval()

    @app.get("/health")
    def health():
        return {"status": "ok", "index_size": faiss_index.ntotal}

    @app.post("/search", response_model=SearchResponse)
    async def search(sketch: UploadFile = File(...), top_k: int = Form(10)):
        img_bytes = await sketch.read()
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        tensor = TRANSFORM(img).unsqueeze(0).to(device)

        with torch.no_grad():
            query_emb = encoder(tensor).cpu().numpy()

        indices, scores = search_index(faiss_index, query_emb,
                                       top_k=top_k, nprobe=config.faiss_nprobe)
        results = [
            SearchResult(model_id=model_ids[idx], score=float(score))
            for idx, score in zip(indices[0], scores[0])
            if idx >= 0
        ]
        return SearchResponse(results=results)

    return app
