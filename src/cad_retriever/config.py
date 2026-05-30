from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # Embedding dimensions
    embed_dim: int = 512
    clip_dim: int = 768

    # Data pipeline
    num_views: int = 6
    image_size: int = 224

    # FAISS
    faiss_nlist: int = 1024
    faiss_nprobe: int = 64

    # Training
    lora_rank: int = 16
    batch_size_phase1: int = 512
    batch_size_phase2: int = 256
    lr_phase1: float = 1e-3
    lr_phase2: float = 5e-4
    temperature: float = 0.07

    # Paths (relative to data_root)
    data_root: Path = field(default_factory=lambda: Path("data"))

    @property
    def abc_raw_dir(self) -> Path:
        return self.data_root / "abc_step"

    @property
    def usd_dir(self) -> Path:
        return self.data_root / "abc_usd"

    @property
    def renders_dir(self) -> Path:
        return self.data_root / "renders"

    @property
    def edges_dir(self) -> Path:
        return self.data_root / "edges"

    @property
    def sketches_dir(self) -> Path:
        return self.data_root / "sketches"

    @property
    def embeddings_dir(self) -> Path:
        return self.data_root / "embeddings"

    @property
    def index_path(self) -> Path:
        return self.data_root / "cad.index"
