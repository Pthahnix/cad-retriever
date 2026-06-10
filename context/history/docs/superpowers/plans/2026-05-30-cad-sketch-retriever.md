# CAD Sketch Retriever Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sketch-based CAD part retrieval system that searches 1M mechanical parts in <10ms using OpenCLIP embeddings and FAISS GPU.

**Architecture:** OpenCLIP ViT-B/16 as frozen backbone with trained projection heads. CAD parts are encoded offline via multi-view rendering → CLIP embedding → projection to 512-dim. Sketch queries go through the same backbone (with LoRA) → projection → FAISS search.

**Tech Stack:** Python 3.11+, PyTorch 2.x, OpenCLIP, FAISS-GPU, Blender 4.x headless, Omniverse Kit CAD Converter, FastAPI, TensorRT 9.x

**Execution Environment:** AutoDL pod (RTX 5090, 2TB data disk at `/home/cc/data`). This plan is executed remotely via `/tmux-cc` → `superpowers:executing-plans`. Working directory: `/home/cc/cad-retriever`. Data outputs go to `/home/cc/data/`.

**Pre-requisite:** Environment setup plan (`2026-05-30-autodl-env-setup.md`) must be fully completed first.

---

## File Structure

```
cad_retriever/
├── pyproject.toml                    # Project config, dependencies
├── src/
│   └── cad_retriever/
│       ├── __init__.py
│       ├── config.py                 # All paths, hyperparams, constants
│       ├── data/
│       │   ├── __init__.py
│       │   ├── download.py           # ABC Dataset download orchestration
│       │   ├── convert.py            # STEP → USD conversion via Omniverse Kit
│       │   ├── render.py             # Blender headless multi-view rendering
│       │   ├── edge_detect.py        # HED + Canny edge detection
│       │   └── sketch_synth.py       # Synthetic sketch generation (perturbations)
│       ├── models/
│       │   ├── __init__.py
│       │   ├── encoder.py            # OpenCLIP wrapper + projection heads
│       │   └── lora.py               # LoRA adapter for sketch encoder
│       ├── training/
│       │   ├── __init__.py
│       │   ├── dataset.py            # PyTorch datasets for Phase 1 & 2
│       │   ├── losses.py             # InfoNCE + view consistency losses
│       │   ├── train_phase1.py       # CAD projection head training
│       │   ├── train_phase2.py       # Sketch→CAD contrastive training
│       │   └── hard_negatives.py     # Hard negative mining logic
│       ├── index/
│       │   ├── __init__.py
│       │   ├── build_index.py        # FAISS index construction
│       │   └── search.py             # Query + rerank logic
│       ├── serving/
│       │   ├── __init__.py
│       │   ├── app.py                # FastAPI application
│       │   └── trt_engine.py         # TensorRT engine loading + inference
│       └── eval/
│           ├── __init__.py
│           ├── metrics.py            # Recall@K, MRR computation
│           └── evaluate.py           # Full evaluation pipeline
├── scripts/
│   ├── download_abc.py               # CLI entry: download ABC dataset
│   ├── convert_all.py                # CLI entry: batch STEP→USD
│   ├── render_all.py                 # CLI entry: batch rendering
│   ├── preprocess_all.py             # CLI entry: edge detect + sketch synth
│   ├── embed_all.py                  # CLI entry: compute all CAD embeddings
│   ├── build_index.py                # CLI entry: build FAISS index
│   ├── train.py                      # CLI entry: run training phases
│   └── evaluate.py                   # CLI entry: run evaluation
└── tests/
    ├── conftest.py                   # Shared fixtures
    ├── test_config.py
    ├── test_encoder.py
    ├── test_lora.py
    ├── test_losses.py
    ├── test_dataset.py
    ├── test_edge_detect.py
    ├── test_sketch_synth.py
    ├── test_index.py
    ├── test_search.py
    ├── test_metrics.py
    └── test_serving.py
```

---

## Task 1: Project Scaffolding & Config

**Files:**
- Create: `pyproject.toml`
- Create: `src/cad_retriever/__init__.py`
- Create: `src/cad_retriever/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write test for config module**

```python
# tests/test_config.py
from cad_retriever.config import Config


def test_config_defaults():
    cfg = Config()
    assert cfg.embed_dim == 512
    assert cfg.clip_dim == 768
    assert cfg.num_views == 6
    assert cfg.image_size == 224
    assert cfg.faiss_nlist == 1024
    assert cfg.faiss_nprobe == 64
    assert cfg.lora_rank == 16
    assert cfg.batch_size_phase1 == 512
    assert cfg.batch_size_phase2 == 256
    assert cfg.lr_phase1 == 1e-3
    assert cfg.lr_phase2 == 5e-4
    assert cfg.temperature == 0.07


def test_config_paths():
    cfg = Config()
    assert cfg.abc_raw_dir.name == "abc_step"
    assert cfg.usd_dir.name == "abc_usd"
    assert cfg.renders_dir.name == "renders"
    assert cfg.edges_dir.name == "edges"
    assert cfg.sketches_dir.name == "sketches"
    assert cfg.embeddings_dir.name == "embeddings"
    assert cfg.index_path.suffix == ".index"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cad_retriever'`

- [ ] **Step 3: Create pyproject.toml**

```toml
# pyproject.toml
[project]
name = "cad-retriever"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "torch>=2.2",
    "open-clip-torch>=2.24",
    "faiss-gpu>=1.10",
    "Pillow>=10.0",
    "numpy>=1.26",
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "pydantic>=2.5",
    "tqdm>=4.66",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=4.1"]
train = ["wandb>=0.16"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/cad_retriever"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 4: Create config module**

```python
# src/cad_retriever/__init__.py
"""CAD Sketch Retriever — sketch-based CAD part retrieval."""

# src/cad_retriever/config.py
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
```

- [ ] **Step 5: Create test conftest**

```python
# tests/conftest.py
import pytest
from pathlib import Path
from cad_retriever.config import Config


@pytest.fixture
def config(tmp_path):
    return Config(data_root=tmp_path)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: project scaffolding with config module"
```

---

## Task 2: OpenCLIP Encoder + Projection Heads

**Files:**
- Create: `src/cad_retriever/models/__init__.py`
- Create: `src/cad_retriever/models/encoder.py`
- Create: `tests/test_encoder.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_encoder.py
import torch
import pytest


def test_cad_encoder_output_shape():
    from cad_retriever.models.encoder import CADEncoder
    enc = CADEncoder(embed_dim=512)
    # 6 views, batch of 2
    images = torch.randn(2, 6, 3, 224, 224)
    out = enc(images)
    assert out.shape == (2, 512)


def test_sketch_encoder_output_shape():
    from cad_retriever.models.encoder import SketchEncoder
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    images = torch.randn(2, 3, 224, 224)
    out = enc(images)
    assert out.shape == (2, 512)


def test_embeddings_are_normalized():
    from cad_retriever.models.encoder import CADEncoder
    enc = CADEncoder(embed_dim=512)
    images = torch.randn(1, 6, 3, 224, 224)
    out = enc(images)
    norm = torch.norm(out, dim=-1)
    assert torch.allclose(norm, torch.ones(1), atol=1e-5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_encoder.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement encoder module**

```python
# src/cad_retriever/models/__init__.py
from .encoder import CADEncoder, SketchEncoder

# src/cad_retriever/models/encoder.py
import torch
import torch.nn as nn
import open_clip


class ProjectionHead(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.linear = nn.Linear(in_dim, out_dim)
        self.norm = nn.LayerNorm(out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.norm(self.linear(x))


class CADEncoder(nn.Module):
    def __init__(self, embed_dim: int = 512, clip_model: str = "ViT-B-16",
                 pretrained: str = "laion2b_s34b_b88k"):
        super().__init__()
        model, _, self.preprocess = open_clip.create_model_and_transforms(
            clip_model, pretrained=pretrained
        )
        self.visual = model.visual
        for param in self.visual.parameters():
            param.requires_grad = False
        self.projection = ProjectionHead(768, embed_dim)

    def encode_single_view(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self.visual(x)

    def forward(self, views: torch.Tensor) -> torch.Tensor:
        """views: (B, num_views, 3, H, W)"""
        B, V, C, H, W = views.shape
        flat = views.reshape(B * V, C, H, W)
        feats = self.encode_single_view(flat)  # (B*V, 768)
        feats = feats.reshape(B, V, -1).mean(dim=1)  # (B, 768)
        out = self.projection(feats)  # (B, 512)
        return nn.functional.normalize(out, dim=-1)


class SketchEncoder(nn.Module):
    def __init__(self, embed_dim: int = 512, lora_rank: int = 16,
                 clip_model: str = "ViT-B-16",
                 pretrained: str = "laion2b_s34b_b88k"):
        super().__init__()
        model, _, self.preprocess = open_clip.create_model_and_transforms(
            clip_model, pretrained=pretrained
        )
        self.visual = model.visual
        for param in self.visual.parameters():
            param.requires_grad = False
        self.projection = ProjectionHead(768, embed_dim)
        self.lora_rank = lora_rank
        # LoRA will be applied in Task 3

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 3, H, W)"""
        with torch.no_grad():
            feats = self.visual(x)  # (B, 768)
        out = self.projection(feats)  # (B, 512)
        return nn.functional.normalize(out, dim=-1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_encoder.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/models/ tests/test_encoder.py
git commit -m "feat: OpenCLIP encoder with projection heads"
```

---

## Task 3: LoRA Adapter

**Files:**
- Create: `src/cad_retriever/models/lora.py`
- Create: `tests/test_lora.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_lora.py
import torch
from cad_retriever.models.lora import apply_lora, count_trainable_params
from cad_retriever.models.encoder import SketchEncoder


def test_lora_applies_to_sketch_encoder():
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    before = count_trainable_params(enc)
    apply_lora(enc.visual, rank=16)
    after = count_trainable_params(enc)
    # LoRA adds trainable params to frozen visual backbone
    assert after > before


def test_lora_output_unchanged_at_init():
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    x = torch.randn(1, 3, 224, 224)
    out_before = enc(x).detach().clone()
    apply_lora(enc.visual, rank=16)
    out_after = enc(x).detach()
    # At init, LoRA B is zero so output should be identical
    assert torch.allclose(out_before, out_after, atol=1e-4)


def test_lora_rank_parameter():
    enc = SketchEncoder(embed_dim=512, lora_rank=8)
    apply_lora(enc.visual, rank=8)
    # Check that LoRA layers exist with correct rank
    found = False
    for name, module in enc.visual.named_modules():
        if hasattr(module, "lora_A"):
            assert module.lora_A.shape[0] == 8
            found = True
            break
    assert found
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lora.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement LoRA module**

```python
# src/cad_retriever/models/lora.py
import torch
import torch.nn as nn
import math


class LoRALinear(nn.Module):
    def __init__(self, original: nn.Linear, rank: int):
        super().__init__()
        self.original = original
        self.original.weight.requires_grad = False
        if self.original.bias is not None:
            self.original.bias.requires_grad = False
        in_features = original.in_features
        out_features = original.out_features
        self.lora_A = nn.Parameter(torch.zeros(rank, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        # B initialized to zero so LoRA is identity at start

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base = self.original(x)
        lora = (x @ self.lora_A.T) @ self.lora_B.T
        return base + lora


def apply_lora(model: nn.Module, rank: int, target_modules: tuple = ("qkv",)):
    for name, module in model.named_modules():
        for target in target_modules:
            if target in name and isinstance(module, nn.Linear):
                parent_name = ".".join(name.split(".")[:-1])
                child_name = name.split(".")[-1]
                parent = dict(model.named_modules())[parent_name] if parent_name else model
                setattr(parent, child_name, LoRALinear(module, rank))


def count_trainable_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lora.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/models/lora.py tests/test_lora.py
git commit -m "feat: LoRA adapter for sketch encoder"
```

---

## Task 4: Loss Functions

**Files:**
- Create: `src/cad_retriever/training/__init__.py`
- Create: `src/cad_retriever/training/losses.py`
- Create: `tests/test_losses.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_losses.py
import torch
from cad_retriever.training.losses import InfoNCELoss, ViewConsistencyLoss


def test_infonce_perfect_match():
    loss_fn = InfoNCELoss(temperature=0.07)
    # Identical embeddings should give low loss
    emb = torch.randn(4, 512)
    emb = torch.nn.functional.normalize(emb, dim=-1)
    loss = loss_fn(emb, emb)
    assert loss.item() < 0.1


def test_infonce_random_gives_higher_loss():
    loss_fn = InfoNCELoss(temperature=0.07)
    a = torch.nn.functional.normalize(torch.randn(32, 512), dim=-1)
    b = torch.nn.functional.normalize(torch.randn(32, 512), dim=-1)
    loss = loss_fn(a, b)
    # Random pairs should give loss close to log(batch_size)
    assert loss.item() > 2.0


def test_view_consistency_same_views():
    loss_fn = ViewConsistencyLoss()
    # 6 identical views should give zero loss
    view_embs = torch.randn(2, 6, 512)
    view_embs = view_embs[:, :1, :].expand(-1, 6, -1)
    loss = loss_fn(view_embs)
    assert loss.item() < 1e-5


def test_infonce_gradient_flows():
    loss_fn = InfoNCELoss(temperature=0.07)
    a = torch.nn.functional.normalize(torch.randn(8, 512, requires_grad=True), dim=-1)
    b = torch.nn.functional.normalize(torch.randn(8, 512), dim=-1)
    loss = loss_fn(a, b)
    loss.backward()
    assert a.grad is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_losses.py -v`
Expected: FAIL

- [ ] **Step 3: Implement losses**

```python
# src/cad_retriever/training/__init__.py
from .losses import InfoNCELoss, ViewConsistencyLoss

# src/cad_retriever/training/losses.py
import torch
import torch.nn as nn
import torch.nn.functional as F


class InfoNCELoss(nn.Module):
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = nn.Parameter(torch.tensor(temperature))

    def forward(self, query_emb: torch.Tensor, key_emb: torch.Tensor) -> torch.Tensor:
        """Symmetric InfoNCE loss.
        query_emb: (B, D) normalized
        key_emb: (B, D) normalized
        """
        logits = query_emb @ key_emb.T / self.temperature  # (B, B)
        labels = torch.arange(logits.shape[0], device=logits.device)
        loss_q2k = F.cross_entropy(logits, labels)
        loss_k2q = F.cross_entropy(logits.T, labels)
        return (loss_q2k + loss_k2q) / 2


class ViewConsistencyLoss(nn.Module):
    def forward(self, view_embeddings: torch.Tensor) -> torch.Tensor:
        """Encourage all views of same CAD to have similar embeddings.
        view_embeddings: (B, num_views, D)
        """
        mean_emb = view_embeddings.mean(dim=1, keepdim=True)  # (B, 1, D)
        diff = view_embeddings - mean_emb  # (B, V, D)
        return (diff ** 2).mean()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_losses.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/training/ tests/test_losses.py
git commit -m "feat: InfoNCE and view consistency losses"
```

---

## Task 5: Edge Detection & Sketch Synthesis

**Files:**
- Create: `src/cad_retriever/data/__init__.py`
- Create: `src/cad_retriever/data/edge_detect.py`
- Create: `src/cad_retriever/data/sketch_synth.py`
- Create: `tests/test_edge_detect.py`
- Create: `tests/test_sketch_synth.py`

- [ ] **Step 1: Write failing tests for edge detection**

```python
# tests/test_edge_detect.py
import numpy as np
from PIL import Image
from cad_retriever.data.edge_detect import detect_edges


def test_detect_edges_output_shape():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img, method="canny")
    assert edges.size == (224, 224)
    assert edges.mode == "L"


def test_detect_edges_binary_output():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img, method="canny")
    arr = np.array(edges)
    unique = np.unique(arr)
    # Canny produces binary edges
    assert len(unique) <= 2
```

- [ ] **Step 2: Write failing tests for sketch synthesis**

```python
# tests/test_sketch_synth.py
import numpy as np
from PIL import Image
from cad_retriever.data.sketch_synth import synthesize_sketch


def test_synthesize_sketch_output_shape():
    edge_img = Image.fromarray(
        np.random.choice([0, 255], (224, 224), p=[0.8, 0.2]).astype(np.uint8)
    )
    sketch = synthesize_sketch(edge_img, difficulty=0.5)
    assert sketch.size == (224, 224)
    assert sketch.mode == "L"


def test_synthesize_sketch_varies_with_difficulty():
    edge_img = Image.fromarray(
        np.random.choice([0, 255], (224, 224), p=[0.7, 0.3]).astype(np.uint8)
    )
    sketch_easy = synthesize_sketch(edge_img, difficulty=0.1)
    sketch_hard = synthesize_sketch(edge_img, difficulty=0.9)
    # Higher difficulty = more perturbation = more different from original
    arr_orig = np.array(edge_img).astype(float)
    diff_easy = np.abs(np.array(sketch_easy).astype(float) - arr_orig).mean()
    diff_hard = np.abs(np.array(sketch_hard).astype(float) - arr_orig).mean()
    assert diff_hard > diff_easy
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_edge_detect.py tests/test_sketch_synth.py -v`
Expected: FAIL

- [ ] **Step 4: Implement edge detection**

```python
# src/cad_retriever/data/__init__.py
from .edge_detect import detect_edges
from .sketch_synth import synthesize_sketch

# src/cad_retriever/data/edge_detect.py
import cv2
import numpy as np
from PIL import Image


def detect_edges(image: Image.Image, method: str = "canny") -> Image.Image:
    """Detect edges from a rendered CAD image.
    Returns a grayscale PIL Image with white edges on black background.
    """
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    if method == "canny":
        edges = cv2.Canny(gray, threshold1=50, threshold2=150)
    else:
        raise ValueError(f"Unknown method: {method}. Use 'canny'.")

    return Image.fromarray(edges, mode="L")
```

- [ ] **Step 5: Implement sketch synthesis**

```python
# src/cad_retriever/data/sketch_synth.py
import cv2
import numpy as np
from PIL import Image


def synthesize_sketch(edge_image: Image.Image, difficulty: float = 0.5) -> Image.Image:
    """Generate a synthetic hand-drawn sketch from an edge image.
    difficulty: 0.0 (clean edges) to 1.0 (heavily perturbed).
    """
    arr = np.array(edge_image).astype(np.float32)

    # Line jitter: randomly shift edge pixels
    if difficulty > 0.1:
        jitter_px = int(difficulty * 3)
        kernel_size = max(1, jitter_px * 2 + 1)
        arr = cv2.GaussianBlur(arr, (kernel_size, kernel_size), sigmaX=difficulty * 2)
        _, arr = cv2.threshold(arr, 80, 255, cv2.THRESH_BINARY)

    # Random line breaks: remove random segments
    if difficulty > 0.3:
        mask = np.random.random(arr.shape) > (difficulty * 0.3)
        arr = arr * mask

    # Thickness variation: dilate with random kernel
    if difficulty > 0.2:
        k = max(1, int(difficulty * 2))
        kernel = np.ones((k, k), np.uint8)
        arr = cv2.dilate(arr.astype(np.uint8), kernel, iterations=1).astype(np.float32)

    # Partial occlusion: black out random rectangles
    if difficulty > 0.6:
        h, w = arr.shape
        num_rects = int(difficulty * 3)
        for _ in range(num_rects):
            rh, rw = np.random.randint(10, 40, size=2)
            ry, rx = np.random.randint(0, h - rh), np.random.randint(0, w - rw)
            arr[ry:ry+rh, rx:rx+rw] = 0

    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), mode="L")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_edge_detect.py tests/test_sketch_synth.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/cad_retriever/data/ tests/test_edge_detect.py tests/test_sketch_synth.py
git commit -m "feat: edge detection and sketch synthesis pipeline"
```

---

## Task 6: Training Datasets

**Files:**
- Create: `src/cad_retriever/training/dataset.py`
- Create: `tests/test_dataset.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_dataset.py
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from cad_retriever.training.dataset import Phase1Dataset, Phase2Dataset


def _create_mock_data(tmp_path: Path, num_models: int = 5, num_views: int = 6):
    renders_dir = tmp_path / "renders"
    edges_dir = tmp_path / "edges"
    sketches_dir = tmp_path / "sketches"
    for d in [renders_dir, edges_dir, sketches_dir]:
        d.mkdir(parents=True)
    model_ids = []
    for i in range(num_models):
        mid = f"model_{i:06d}"
        model_ids.append(mid)
        (renders_dir / mid).mkdir()
        (edges_dir / mid).mkdir()
        (sketches_dir / mid).mkdir()
        for v in range(num_views):
            img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
            img.save(renders_dir / mid / f"view_{v}.png")
            edge = Image.fromarray(np.random.randint(0, 255, (224, 224), dtype=np.uint8))
            edge.save(edges_dir / mid / f"view_{v}.png")
            edge.save(sketches_dir / mid / f"view_{v}.png")
    return model_ids


def test_phase1_dataset_returns_views(tmp_path):
    model_ids = _create_mock_data(tmp_path)
    ds = Phase1Dataset(renders_dir=tmp_path / "renders", model_ids=model_ids, num_views=6)
    item = ds[0]
    assert item["views"].shape == (6, 3, 224, 224)
    assert item["model_id"] == model_ids[0]


def test_phase2_dataset_returns_sketch_and_embedding(tmp_path):
    model_ids = _create_mock_data(tmp_path)
    # Create fake precomputed embeddings
    emb_dir = tmp_path / "embeddings"
    emb_dir.mkdir()
    for mid in model_ids:
        np.save(emb_dir / f"{mid}.npy", np.random.randn(512).astype(np.float32))
    ds = Phase2Dataset(
        sketches_dir=tmp_path / "sketches",
        embeddings_dir=emb_dir,
        model_ids=model_ids,
        num_views=6,
    )
    item = ds[0]
    assert item["sketch"].shape == (3, 224, 224)
    assert item["cad_embedding"].shape == (512,)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dataset.py -v`
Expected: FAIL

- [ ] **Step 3: Implement datasets**

```python
# src/cad_retriever/training/dataset.py
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
            img = Image.open(self.renders_dir / mid / f"view_{v}.png").convert("RGB")
            views.append(TRANSFORM(img))
        return {"views": torch.stack(views), "model_id": mid}


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
        sketch = Image.open(sketch_path).convert("RGB")
        sketch_tensor = TRANSFORM(sketch)
        cad_emb = np.load(self.embeddings_dir / f"{mid}.npy")
        return {
            "sketch": sketch_tensor,
            "cad_embedding": torch.from_numpy(cad_emb),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dataset.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/training/dataset.py tests/test_dataset.py
git commit -m "feat: Phase 1 and Phase 2 training datasets"
```

---

## Task 7: FAISS Index Build & Search

**Files:**
- Create: `src/cad_retriever/index/__init__.py`
- Create: `src/cad_retriever/index/build_index.py`
- Create: `src/cad_retriever/index/search.py`
- Create: `tests/test_index.py`
- Create: `tests/test_search.py`

- [ ] **Step 1: Write failing test for index building**

```python
# tests/test_index.py
import numpy as np
import faiss
from pathlib import Path
from cad_retriever.index.build_index import build_faiss_index, load_faiss_index


def test_build_index_creates_file(tmp_path):
    vectors = np.random.randn(1000, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=32)
    assert index_path.exists()


def test_build_index_correct_size(tmp_path):
    vectors = np.random.randn(1000, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=32)
    index = load_faiss_index(index_path)
    assert index.ntotal == 1000
```

- [ ] **Step 2: Write failing test for search**

```python
# tests/test_search.py
import numpy as np
from cad_retriever.index.search import search_index
from cad_retriever.index.build_index import build_faiss_index, load_faiss_index


def test_search_finds_exact_match(tmp_path):
    vectors = np.random.randn(100, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=10)
    index = load_faiss_index(index_path)
    # Search for the first vector — should find itself
    query = vectors[0:1]
    indices, scores = search_index(index, query, top_k=5, nprobe=10)
    assert indices[0][0] == 0
    assert scores[0][0] > 0.99


def test_search_returns_correct_shape(tmp_path):
    vectors = np.random.randn(100, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "test.index"
    build_faiss_index(vectors, index_path, nlist=10)
    index = load_faiss_index(index_path)
    query = np.random.randn(3, 512).astype(np.float32)
    query = query / np.linalg.norm(query, axis=1, keepdims=True)
    indices, scores = search_index(index, query, top_k=10, nprobe=10)
    assert indices.shape == (3, 10)
    assert scores.shape == (3, 10)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_index.py tests/test_search.py -v`
Expected: FAIL

- [ ] **Step 4: Implement index building**

```python
# src/cad_retriever/index/__init__.py
from .build_index import build_faiss_index, load_faiss_index
from .search import search_index

# src/cad_retriever/index/build_index.py
import numpy as np
import faiss
from pathlib import Path


def build_faiss_index(vectors: np.ndarray, index_path: Path, nlist: int = 1024):
    """Build and save a FAISS IVFFlat index with inner product metric."""
    d = vectors.shape[1]
    quantizer = faiss.IndexFlatIP(d)
    index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_INNER_PRODUCT)
    index.train(vectors)
    index.add(vectors)
    faiss.write_index(index, str(index_path))


def load_faiss_index(index_path: Path) -> faiss.Index:
    """Load a FAISS index from disk."""
    return faiss.read_index(str(index_path))
```

- [ ] **Step 5: Implement search**

```python
# src/cad_retriever/index/search.py
import numpy as np
import faiss


def search_index(
    index: faiss.Index,
    query: np.ndarray,
    top_k: int = 100,
    nprobe: int = 64,
) -> tuple[np.ndarray, np.ndarray]:
    """Search FAISS index. Returns (indices, scores) both shape (n_queries, top_k)."""
    index.nprobe = nprobe
    scores, indices = index.search(query, top_k)
    return indices, scores
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_index.py tests/test_search.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/cad_retriever/index/ tests/test_index.py tests/test_search.py
git commit -m "feat: FAISS index build and search"
```

---

## Task 8: Evaluation Metrics

**Files:**
- Create: `src/cad_retriever/eval/__init__.py`
- Create: `src/cad_retriever/eval/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_metrics.py
import numpy as np
from cad_retriever.eval.metrics import recall_at_k, mean_reciprocal_rank


def test_recall_at_1_perfect():
    # Ground truth is index 0, retrieved [0, 1, 2, ...]
    retrieved = np.array([[0, 1, 2, 3, 4]])
    ground_truth = np.array([0])
    assert recall_at_k(retrieved, ground_truth, k=1) == 1.0


def test_recall_at_1_miss():
    retrieved = np.array([[5, 1, 2, 3, 4]])
    ground_truth = np.array([0])
    assert recall_at_k(retrieved, ground_truth, k=1) == 0.0


def test_recall_at_10_hit():
    retrieved = np.array([[5, 1, 2, 3, 4, 6, 7, 8, 9, 0]])
    ground_truth = np.array([0])
    assert recall_at_k(retrieved, ground_truth, k=10) == 1.0


def test_mrr_first_position():
    retrieved = np.array([[0, 1, 2]])
    ground_truth = np.array([0])
    assert mean_reciprocal_rank(retrieved, ground_truth) == 1.0


def test_mrr_third_position():
    retrieved = np.array([[5, 6, 0, 1, 2]])
    ground_truth = np.array([0])
    assert mean_reciprocal_rank(retrieved, ground_truth) == 1.0 / 3


def test_mrr_batch():
    retrieved = np.array([[0, 1, 2], [3, 0, 1]])
    ground_truth = np.array([0, 0])
    # First query: rank 1 (1/1), second query: rank 2 (1/2)
    assert mean_reciprocal_rank(retrieved, ground_truth) == (1.0 + 0.5) / 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL

- [ ] **Step 3: Implement metrics**

```python
# src/cad_retriever/eval/__init__.py
from .metrics import recall_at_k, mean_reciprocal_rank

# src/cad_retriever/eval/metrics.py
import numpy as np


def recall_at_k(retrieved: np.ndarray, ground_truth: np.ndarray, k: int) -> float:
    """Compute Recall@K.
    retrieved: (n_queries, n_retrieved) — ranked indices
    ground_truth: (n_queries,) — correct index for each query
    """
    n = len(ground_truth)
    hits = 0
    for i in range(n):
        if ground_truth[i] in retrieved[i, :k]:
            hits += 1
    return hits / n


def mean_reciprocal_rank(retrieved: np.ndarray, ground_truth: np.ndarray) -> float:
    """Compute MRR.
    retrieved: (n_queries, n_retrieved)
    ground_truth: (n_queries,)
    """
    n = len(ground_truth)
    rr_sum = 0.0
    for i in range(n):
        positions = np.where(retrieved[i] == ground_truth[i])[0]
        if len(positions) > 0:
            rr_sum += 1.0 / (positions[0] + 1)
    return rr_sum / n
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_metrics.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/eval/ tests/test_metrics.py
git commit -m "feat: recall@K and MRR evaluation metrics"
```

---

## Task 9: Training Scripts (Phase 1 & 2)

**Files:**
- Create: `src/cad_retriever/training/train_phase1.py`
- Create: `src/cad_retriever/training/train_phase2.py`
- Create: `src/cad_retriever/training/hard_negatives.py`
- Create: `scripts/train.py`

- [ ] **Step 1: Implement Phase 1 training loop**

```python
# src/cad_retriever/training/train_phase1.py
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
            feats = encoder.encode_single_view(flat)  # (B*V, 768)
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
```

- [ ] **Step 2: Implement Phase 2 training loop**

```python
# src/cad_retriever/training/train_phase2.py
import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from pathlib import Path
from tqdm import tqdm

from cad_retriever.config import Config
from cad_retriever.models.encoder import SketchEncoder
from cad_retriever.models.lora import apply_lora, count_trainable_params
from cad_retriever.training.dataset import Phase2Dataset
from cad_retriever.training.losses import InfoNCELoss


def train_phase2(config: Config, model_ids: list[str], num_epochs: int = 10):
    device = torch.device("cuda")
    encoder = SketchEncoder(embed_dim=config.embed_dim, lora_rank=config.lora_rank)
    apply_lora(encoder.visual, rank=config.lora_rank)
    encoder = encoder.to(device)

    loss_fn = InfoNCELoss(temperature=config.temperature).to(device)

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
            sketch_embs = encoder(sketches)
            cad_embs = torch.nn.functional.normalize(cad_embs, dim=-1)
            loss = loss_fn(sketch_embs, cad_embs)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            total_loss += loss.item()
        avg_loss = total_loss / len(loader)
        print(f"Epoch {epoch+1}: loss={avg_loss:.4f}, tau={loss_fn.temperature.item():.4f}")

    torch.save(encoder.state_dict(), config.data_root / "sketch_encoder.pt")
    return encoder
```

- [ ] **Step 3: Implement hard negative mining**

```python
# src/cad_retriever/training/hard_negatives.py
import numpy as np
import faiss
from pathlib import Path


def mine_hard_negatives(
    embeddings_dir: Path,
    model_ids: list[str],
    top_k: int = 50,
    hard_range: tuple[int, int] = (5, 20),
) -> dict[str, list[str]]:
    """For each model, find hard negatives (rank 5-20 in current embedding space)."""
    vectors = []
    for mid in model_ids:
        vec = np.load(embeddings_dir / f"{mid}.npy")
        vectors.append(vec)
    vectors = np.stack(vectors).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    d = vectors.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(vectors)
    _, indices = index.search(vectors, top_k)

    hard_negs = {}
    lo, hi = hard_range
    for i, mid in enumerate(model_ids):
        neg_indices = indices[i, lo:hi]
        hard_negs[mid] = [model_ids[j] for j in neg_indices]
    return hard_negs
```

- [ ] **Step 4: Create CLI training script**

```python
# scripts/train.py
"""CLI entry point for training phases."""
import argparse
from pathlib import Path
from cad_retriever.config import Config


def main():
    parser = argparse.ArgumentParser(description="Train CAD Sketch Retriever")
    parser.add_argument("--phase", type=int, choices=[1, 2], required=True)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()

    config = Config(data_root=args.data_root)

    # Load model IDs from manifest
    manifest = config.data_root / "model_ids.txt"
    model_ids = manifest.read_text().strip().split("\n")
    print(f"Loaded {len(model_ids)} model IDs")

    if args.phase == 1:
        from cad_retriever.training.train_phase1 import train_phase1
        train_phase1(config, model_ids)
    elif args.phase == 2:
        from cad_retriever.training.train_phase2 import train_phase2
        train_phase2(config, model_ids, num_epochs=args.epochs)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/training/train_phase1.py \
        src/cad_retriever/training/train_phase2.py \
        src/cad_retriever/training/hard_negatives.py \
        scripts/train.py
git commit -m "feat: training loops for Phase 1 and Phase 2"
```

---

## Task 10: Data Pipeline Scripts (Download, Convert, Render)

**Files:**
- Create: `src/cad_retriever/data/download.py`
- Create: `src/cad_retriever/data/render.py`
- Create: `src/cad_retriever/data/convert.py`
- Create: `scripts/download_abc.py`
- Create: `scripts/render_all.py`
- Create: `scripts/preprocess_all.py`
- Create: `scripts/embed_all.py`
- Create: `scripts/build_index.py`

- [ ] **Step 1: Implement ABC Dataset download**

```python
# src/cad_retriever/data/download.py
"""Download the full ABC Dataset (1M STEP files).
HARD REQUIREMENT: All 1M files must be fully downloaded before any processing begins.
"""
import subprocess
from pathlib import Path
from tqdm import tqdm


ABC_CHUNKS_URL = "https://archive.nyu.edu/rest/bitstreams/{chunk_id}/retrieve"
# ABC dataset is distributed as ~8000 .7z chunks
ABC_MANIFEST_URL = "https://deep-geometry.github.io/abc-dataset/data/abc_chunk_ids.txt"


def download_abc_dataset(output_dir: Path, verify: bool = True):
    """Download all ABC dataset chunks and extract STEP files.
    This downloads the COMPLETE 1M dataset. No partial downloads allowed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "chunk_ids.txt"

    # Download manifest
    subprocess.run(
        ["curl", "-o", str(manifest_path), ABC_MANIFEST_URL],
        check=True,
    )
    chunk_ids = manifest_path.read_text().strip().split("\n")
    print(f"ABC Dataset: {len(chunk_ids)} chunks to download")

    # Download each chunk
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    for chunk_id in tqdm(chunk_ids, desc="Downloading ABC chunks"):
        chunk_path = chunks_dir / f"{chunk_id}.7z"
        if chunk_path.exists():
            continue
        url = ABC_CHUNKS_URL.format(chunk_id=chunk_id)
        subprocess.run(["curl", "-o", str(chunk_path), url], check=True)

    # Extract all chunks
    step_dir = output_dir / "step"
    step_dir.mkdir(exist_ok=True)
    for chunk_file in tqdm(sorted(chunks_dir.glob("*.7z")), desc="Extracting"):
        subprocess.run(
            ["7z", "x", str(chunk_file), f"-o{step_dir}", "-y", "*.step"],
            check=True, capture_output=True,
        )

    # Verify count
    step_files = list(step_dir.rglob("*.step"))
    print(f"Downloaded and extracted {len(step_files)} STEP files")
    if verify and len(step_files) < 900_000:
        raise RuntimeError(
            f"Expected ~1M STEP files, got {len(step_files)}. "
            "Download may be incomplete."
        )

    # Write model ID manifest
    model_ids = sorted([f.stem for f in step_files])
    (output_dir / "model_ids.txt").write_text("\n".join(model_ids))
    return model_ids
```

- [ ] **Step 2: Implement Blender rendering script**

```python
# src/cad_retriever/data/render.py
"""Batch render CAD models to 6 standard views using Blender headless."""
import subprocess
import json
from pathlib import Path
from tqdm import tqdm

# 6 standard views: front, back, left, right, top, bottom
CAMERA_ANGLES = [
    (0, 0, 0),      # front
    (0, 180, 0),    # back
    (0, 90, 0),     # left
    (0, -90, 0),    # right
    (90, 0, 0),     # top
    (-90, 0, 0),    # bottom
]

BLENDER_SCRIPT = '''
import bpy
import sys
import json
import math

args = json.loads(sys.argv[sys.argv.index("--") + 1])
input_path = args["input"]
output_dir = args["output_dir"]
image_size = args["image_size"]
angles = args["angles"]

# Clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import USD/OBJ
if input_path.endswith(".usd") or input_path.endswith(".usda") or input_path.endswith(".usdc"):
    bpy.ops.wm.usd_open(filepath=input_path)
else:
    bpy.ops.import_mesh.stl(filepath=input_path)

# Setup render
bpy.context.scene.render.resolution_x = image_size
bpy.context.scene.render.resolution_y = image_size
bpy.context.scene.render.image_settings.file_format = "PNG"

# Add camera and light
bpy.ops.object.camera_add()
cam = bpy.context.active_object
bpy.context.scene.camera = cam

bpy.ops.object.light_add(type="SUN")

# Auto-frame object
bpy.ops.object.select_all(action="SELECT")
bpy.ops.view3d.camera_to_view_selected()

# Render each view
for i, (rx, ry, rz) in enumerate(angles):
    cam.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    bpy.context.scene.render.filepath = f"{output_dir}/view_{i}.png"
    bpy.ops.render.render(write_still=True)
'''


def render_model(input_path: Path, output_dir: Path, image_size: int = 224):
    """Render a single CAD model to 6 views using Blender."""
    output_dir.mkdir(parents=True, exist_ok=True)
    args_json = json.dumps({
        "input": str(input_path),
        "output_dir": str(output_dir),
        "image_size": image_size,
        "angles": CAMERA_ANGLES,
    })
    subprocess.run(
        ["blender", "--background", "--python-expr", BLENDER_SCRIPT, "--", args_json],
        check=True, capture_output=True,
    )


def render_all(input_dir: Path, output_dir: Path, image_size: int = 224):
    """Render all models in input_dir."""
    files = sorted(input_dir.rglob("*.usd")) + sorted(input_dir.rglob("*.usda"))
    if not files:
        files = sorted(input_dir.rglob("*.step"))
    print(f"Rendering {len(files)} models")
    for f in tqdm(files, desc="Rendering"):
        model_id = f.stem
        model_out = output_dir / model_id
        if (model_out / "view_5.png").exists():
            continue
        render_model(f, model_out, image_size)
```

- [ ] **Step 3: Implement STEP→USD conversion**

```python
# src/cad_retriever/data/convert.py
"""Convert STEP files to OpenUSD format."""
import subprocess
from pathlib import Path
from tqdm import tqdm


def convert_step_to_usd(step_path: Path, usd_path: Path):
    """Convert a single STEP file to USD using Omniverse Kit CAD Converter.
    Falls back to OCP mesh export if converter unavailable.
    """
    usd_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["omni_cad_converter", "--input", str(step_path), "--output", str(usd_path)],
            check=True, capture_output=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        _fallback_ocp_convert(step_path, usd_path)


def _fallback_ocp_convert(step_path: Path, usd_path: Path):
    """Fallback: convert STEP to OBJ via OCP, then to USD via usdcat."""
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(step_path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Failed to read STEP: {step_path}")
    reader.TransferRoots()
    shape = reader.OneShape()

    mesh = BRepMesh_IncrementalMesh(shape, 0.1)
    mesh.Perform()

    stl_path = usd_path.with_suffix(".stl")
    writer = StlAPI_Writer()
    writer.Write(shape, str(stl_path))

    # Convert STL to USD via usdcat (if available)
    try:
        subprocess.run(["usdcat", str(stl_path), "-o", str(usd_path)],
                       check=True, capture_output=True)
        stl_path.unlink()
    except FileNotFoundError:
        usd_path.with_suffix(".stl").rename(usd_path.with_suffix(".stl"))


def convert_all(step_dir: Path, usd_dir: Path):
    """Convert all STEP files to USD."""
    step_files = sorted(step_dir.rglob("*.step"))
    print(f"Converting {len(step_files)} STEP files to USD")
    failed = []
    for f in tqdm(step_files, desc="Converting STEP→USD"):
        out = usd_dir / f"{f.stem}.usd"
        if out.exists():
            continue
        try:
            convert_step_to_usd(f, out)
        except Exception as e:
            failed.append((f.name, str(e)))
    if failed:
        fail_log = usd_dir / "conversion_failures.txt"
        fail_log.write_text("\n".join(f"{n}: {e}" for n, e in failed))
        print(f"WARNING: {len(failed)} conversions failed. See {fail_log}")
```

- [ ] **Step 4: Create CLI scripts**

```python
# scripts/download_abc.py
"""Download the complete ABC Dataset (1M STEP files)."""
import argparse
from pathlib import Path
from cad_retriever.data.download import download_abc_dataset

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=Path("data/abc_step"))
args = parser.parse_args()
download_abc_dataset(args.output)
```

```python
# scripts/render_all.py
"""Render all CAD models to multi-view images."""
import argparse
from pathlib import Path
from cad_retriever.data.render import render_all

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, default=Path("data/abc_usd"))
parser.add_argument("--output", type=Path, default=Path("data/renders"))
parser.add_argument("--size", type=int, default=224)
args = parser.parse_args()
render_all(args.input, args.output, args.size)
```

```python
# scripts/preprocess_all.py
"""Generate edge maps and synthetic sketches for all rendered models."""
import argparse
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from cad_retriever.data.edge_detect import detect_edges
from cad_retriever.data.sketch_synth import synthesize_sketch
import random

parser = argparse.ArgumentParser()
parser.add_argument("--renders", type=Path, default=Path("data/renders"))
parser.add_argument("--edges-out", type=Path, default=Path("data/edges"))
parser.add_argument("--sketches-out", type=Path, default=Path("data/sketches"))
args = parser.parse_args()

model_dirs = sorted(args.renders.iterdir())
print(f"Processing {len(model_dirs)} models")
for model_dir in tqdm(model_dirs):
    if not model_dir.is_dir():
        continue
    mid = model_dir.name
    edge_dir = args.edges_out / mid
    sketch_dir = args.sketches_out / mid
    edge_dir.mkdir(parents=True, exist_ok=True)
    sketch_dir.mkdir(parents=True, exist_ok=True)
    for view_file in sorted(model_dir.glob("view_*.png")):
        img = Image.open(view_file)
        edge = detect_edges(img, method="canny")
        edge.save(edge_dir / view_file.name)
        difficulty = random.uniform(0.2, 0.8)
        sketch = synthesize_sketch(edge, difficulty=difficulty)
        sketch.save(sketch_dir / view_file.name)
```

```python
# scripts/embed_all.py
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
parser.add_argument("--data-root", type=Path, default=Path("data"))
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
loader = DataLoader(dataset, batch_size=64, num_workers=8, pin_memory=True)

config.embeddings_dir.mkdir(parents=True, exist_ok=True)
with torch.no_grad():
    for batch in tqdm(loader, desc="Computing embeddings"):
        views = batch["views"].to(device)
        embs = encoder(views).cpu().numpy()
        for mid, emb in zip(batch["model_id"], embs):
            np.save(config.embeddings_dir / f"{mid}.npy", emb)
```

```python
# scripts/build_index.py
"""Build FAISS index from all precomputed CAD embeddings."""
import argparse
import numpy as np
from pathlib import Path
from tqdm import tqdm
from cad_retriever.config import Config
from cad_retriever.index.build_index import build_faiss_index

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, default=Path("data"))
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
```

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/data/download.py src/cad_retriever/data/render.py \
        src/cad_retriever/data/convert.py scripts/
git commit -m "feat: data pipeline scripts (download, convert, render, embed, index)"
```

---

## Task 11: FastAPI Serving

**Files:**
- Create: `src/cad_retriever/serving/__init__.py`
- Create: `src/cad_retriever/serving/app.py`
- Create: `tests/test_serving.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_serving.py
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_app(tmp_path):
    # Create minimal index and model files for testing
    from cad_retriever.index.build_index import build_faiss_index
    vectors = np.random.randn(100, 512).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    index_path = tmp_path / "cad.index"
    build_faiss_index(vectors, index_path, nlist=10)
    model_ids = [f"model_{i:06d}" for i in range(100)]
    (tmp_path / "model_ids.txt").write_text("\n".join(model_ids))

    with patch("cad_retriever.serving.app.get_config") as mock_cfg:
        from cad_retriever.config import Config
        cfg = Config(data_root=tmp_path)
        mock_cfg.return_value = cfg
        from cad_retriever.serving.app import create_app
        app = create_app(index_path=index_path, model_ids=model_ids)
        yield TestClient(app)


def test_health_endpoint(mock_app):
    resp = mock_app.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_search_endpoint_returns_results(mock_app):
    # Create a dummy sketch image (224x224 white)
    from PIL import Image
    import io
    img = Image.new("RGB", (224, 224), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = mock_app.post("/search", files={"sketch": ("test.png", buf, "image/png")},
                         data={"top_k": "5"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 5
    assert "model_id" in results[0]
    assert "score" in results[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_serving.py -v`
Expected: FAIL

- [ ] **Step 3: Implement FastAPI app**

```python
# src/cad_retriever/serving/__init__.py
from .app import create_app

# src/cad_retriever/serving/app.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_serving.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/serving/ tests/test_serving.py
git commit -m "feat: FastAPI serving endpoint for sketch search"
```

---

## Task 12: Evaluation Pipeline

**Files:**
- Create: `src/cad_retriever/eval/evaluate.py`
- Create: `scripts/evaluate.py`

- [ ] **Step 1: Implement evaluation pipeline**

```python
# src/cad_retriever/eval/evaluate.py
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
            # Ground truth: the model this sketch came from
            # Phase2Dataset iterates (model_id, view) pairs in order
            # We need to map back — using the dataset's _entries
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
```

- [ ] **Step 2: Create CLI evaluation script**

```python
# scripts/evaluate.py
"""Run evaluation on test set."""
import argparse
import json
from pathlib import Path
from cad_retriever.config import Config
from cad_retriever.eval.evaluate import evaluate

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, default=Path("data"))
parser.add_argument("--test-size", type=int, default=5000)
args = parser.parse_args()

config = Config(data_root=args.data_root)
all_model_ids = (config.data_root / "model_ids.txt").read_text().strip().split("\n")

# Split: last N models as test set
test_ids = all_model_ids[-args.test_size:]
print(f"Evaluating on {len(test_ids)} test models ({len(test_ids) * config.num_views} queries)")

results = evaluate(config, test_ids, all_model_ids)
print("\n=== Evaluation Results ===")
for k, v in results.items():
    print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

# Save results
results_path = config.data_root / "eval_results.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {results_path}")

# Check against targets
targets = {"recall@1": 0.60, "recall@10": 0.90, "mrr": 0.70}
all_pass = True
for metric, target in targets.items():
    if results[metric] < target:
        print(f"  BELOW TARGET: {metric} = {results[metric]:.4f} < {target}")
        all_pass = False

if all_pass:
    print("\nAll targets met!")
else:
    print("\nSome targets not met. Consider upgrading to next fallback level.")
```

- [ ] **Step 3: Commit**

```bash
git add src/cad_retriever/eval/evaluate.py scripts/evaluate.py
git commit -m "feat: evaluation pipeline with target checking"
```

---

## Task 13: TensorRT Optimization (Post-Training)

**Files:**
- Create: `src/cad_retriever/serving/trt_engine.py`

- [ ] **Step 1: Implement TensorRT export and inference**

```python
# src/cad_retriever/serving/trt_engine.py
"""TensorRT engine export and inference for production serving."""
import torch
import numpy as np
from pathlib import Path


def export_to_onnx(encoder, output_path: Path, image_size: int = 224):
    """Export sketch encoder to ONNX for TensorRT compilation."""
    encoder.eval()
    dummy_input = torch.randn(1, 3, image_size, image_size).cuda()
    torch.onnx.export(
        encoder,
        dummy_input,
        str(output_path),
        input_names=["image"],
        output_names=["embedding"],
        dynamic_axes={"image": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version=17,
    )
    print(f"ONNX model exported to {output_path}")


def build_trt_engine(onnx_path: Path, engine_path: Path, fp16: bool = True):
    """Build TensorRT engine from ONNX model.
    Requires: tensorrt Python package installed.
    Run: trtexec --onnx=model.onnx --saveEngine=model.engine --fp16
    """
    import subprocess
    cmd = [
        "trtexec",
        f"--onnx={onnx_path}",
        f"--saveEngine={engine_path}",
        "--minShapes=image:1x3x224x224",
        "--optShapes=image:1x3x224x224",
        "--maxShapes=image:16x3x224x224",
    ]
    if fp16:
        cmd.append("--fp16")
    subprocess.run(cmd, check=True)
    print(f"TensorRT engine saved to {engine_path}")


class TRTInference:
    """TensorRT inference wrapper. Falls back to PyTorch if TRT unavailable."""

    def __init__(self, engine_path: Path | None = None, encoder=None):
        self.trt_available = False
        self.encoder = encoder
        if engine_path and engine_path.exists():
            try:
                import tensorrt as trt
                self._load_engine(engine_path)
                self.trt_available = True
            except ImportError:
                pass

    def _load_engine(self, engine_path: Path):
        import tensorrt as trt
        logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f:
            self.engine = trt.Runtime(logger).deserialize_cuda_engine(f.read())
        self.context = self.engine.create_execution_context()

    def infer(self, image_tensor: torch.Tensor) -> np.ndarray:
        if self.trt_available:
            return self._infer_trt(image_tensor)
        with torch.no_grad():
            return self.encoder(image_tensor).cpu().numpy()

    def _infer_trt(self, image_tensor: torch.Tensor) -> np.ndarray:
        # Simplified TRT inference — real implementation needs proper buffer management
        batch_size = image_tensor.shape[0]
        self.context.set_input_shape("image", image_tensor.shape)
        output = torch.empty(batch_size, 512, device="cuda")
        self.context.execute_v2([image_tensor.data_ptr(), output.data_ptr()])
        return output.cpu().numpy()
```

- [ ] **Step 2: Commit**

```bash
git add src/cad_retriever/serving/trt_engine.py
git commit -m "feat: TensorRT export and inference wrapper"
```

---

## Execution Order Summary

The pipeline must be executed in strict order:

1. **Tasks 1-8**: Code implementation (can be done without data)
2. **Task 10 Step 1**: Download full ABC Dataset (1M STEP files)
3. **Task 10 Step 3**: Convert all 1M STEP → USD
4. **Task 10 Step 2**: Render all 1M models (6 views each)
5. **Task 10 Step 4 (preprocess_all)**: Generate edges + sketches for all 1M
6. **Task 9 Phase 1**: Train projection head A
7. **Task 10 Step 4 (embed_all)**: Compute all 1M CAD embeddings
8. **Task 10 Step 4 (build_index)**: Build FAISS index
9. **Task 9 Phase 2**: Train sketch encoder
10. **Task 12**: Evaluate → check against targets
11. **Task 13**: TensorRT optimization (if latency needs it)
12. **Task 11**: Deploy serving endpoint

**HARD CONSTRAINT**: Steps 2-5 each require ALL 1M models to complete before proceeding.
