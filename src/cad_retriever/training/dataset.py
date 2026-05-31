import random
import numpy as np
import torch
from torch.utils.data import Dataset
from pathlib import Path
from PIL import Image
from torchvision import transforms


CLIP_NORMALIZE = transforms.Normalize(
    mean=(0.48145466, 0.4578275, 0.40821073),
    std=(0.26862954, 0.26130258, 0.27577711),
)

TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    CLIP_NORMALIZE,
])


class Phase1Dataset(Dataset):
    def __init__(self, renders_dir: Path, model_ids: list[str], num_views: int = 6):
        self.renders_dir = Path(renders_dir)
        self.model_ids = model_ids
        self.num_views = num_views

    def __len__(self) -> int:
        return len(self.model_ids)

    def __getitem__(self, idx: int) -> dict:
        mid = self.model_ids[idx]
        views = []
        for v in range(self.num_views):
            try:
                img = Image.open(self.renders_dir / mid / f"view_{v}.png").convert("RGB")
                views.append(TRANSFORM(img))
            except Exception:
                views.append(torch.zeros(3, 224, 224))
        return {"views": torch.stack(views), "model_id": mid}


class Phase1ContrastiveDataset(Dataset):
    """Returns two random views of the same model for contrastive learning."""

    def __init__(self, renders_dir: Path, model_ids: list[str], num_views: int = 6):
        self.renders_dir = Path(renders_dir)
        self.model_ids = model_ids
        self.num_views = num_views

    def __len__(self) -> int:
        return len(self.model_ids)

    def __getitem__(self, idx: int) -> dict:
        mid = self.model_ids[idx]
        views = list(range(self.num_views))
        v_a, v_b = random.sample(views, 2)
        img_a = Image.open(self.renders_dir / mid / f"view_{v_a}.png").convert("RGB")
        img_b = Image.open(self.renders_dir / mid / f"view_{v_b}.png").convert("RGB")
        return {
            "view_a": TRANSFORM(img_a),
            "view_b": TRANSFORM(img_b),
            "model_id": mid,
        }


class Phase2Dataset(Dataset):
    def __init__(self, sketches_dir: Path, embeddings_dir: Path,
                 model_ids: list[str], num_views: int = 6):
        self.sketches_dir = Path(sketches_dir)
        self.embeddings_dir = Path(embeddings_dir)
        self.model_ids = model_ids
        self.num_views = num_views
        self._entries = []
        for mid in model_ids:
            for v in range(num_views):
                self._entries.append((mid, v))

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, idx: int) -> dict:
        mid, v = self._entries[idx]
        sketch_path = self.sketches_dir / mid / f"view_{v}.png"
        try:
            sketch = Image.open(sketch_path).convert("RGB")
            sketch_tensor = TRANSFORM(sketch)
        except Exception:
            sketch_tensor = torch.zeros(3, 224, 224)
        cad_emb = np.load(self.embeddings_dir / f"{mid}.npy")
        return {
            "sketch": sketch_tensor,
            "cad_embedding": torch.from_numpy(cad_emb),
        }

