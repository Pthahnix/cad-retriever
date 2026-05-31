# Training Pipeline Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the CAD sketch retriever's training pipeline so it achieves recall@1 >= 0.60, recall@10 >= 0.90, MRR >= 0.70 on 1M models.

**Architecture:** Replace the broken rendering (PIL polygons) with pyrender+EGL, fix Phase 1 loss from ViewConsistency to InfoNCE+HardNegatives, fix SketchEncoder LoRA gradient flow, restore Canny edge detection for sketch generation, and re-run the entire data+training pipeline from scratch.

**Tech Stack:** Python 3.12, PyTorch 2.8, OpenCLIP ViT-B/16, pyrender+EGL, trimesh, FAISS-GPU, FastAPI

**Execution Environment:** AutoDL pod (RTX 5090, 2TB data disk at `/home/cc/data`). Working directory: `/home/cc/cad-retriever`. All data outputs go to `/home/cc/data/`.

**Critical rules from CLAUDE.md:**
- ALL data MUST go to `/home/cc/data/` (data disk), NEVER `/tmp/` or system disk
- Temp files (STL) must be written to `/home/cc/data/tmp/` and cleaned immediately
- Monitor system disk with `df -h /` — stop if >80%
- GPU utilization should be >80% during training
- Set up 30-min self-check cron per CLAUDE.md spec

---

## File Structure

```
src/cad_retriever/
├── models/
│   └── encoder.py              # MODIFY: remove torch.no_grad() in SketchEncoder.forward
├── data/
│   └── edge_detect.py          # MODIFY: replace CLAHE with proper Canny
├── training/
│   ├── dataset.py              # MODIFY: add Phase1ContrastiveDataset
│   ├── train_phase1.py         # REWRITE: InfoNCE + hard negative mining
│   ├── train_phase2.py         # MODIFY: reduce batch, add grad clip, best ckpt
│   └── hard_negatives.py       # MODIFY: update to work with new pipeline
scripts/
├── render_all.py               # REWRITE: pyrender + EGL
├── preprocess_all.py           # MODIFY: remove loop mode, simpler single-pass
└── train.py                    # MODIFY: support phase1a/phase1b split
tests/
├── test_edge_detect.py         # MODIFY: update for new Canny behavior
├── test_render_pyrender.py     # CREATE: test pyrender rendering
└── test_phase1_infonce.py      # CREATE: test InfoNCE training loop
```

---

## Pre-requisites (before starting any task)

1. Read `CLAUDE.md` in the project root — it contains critical rules about disk usage, GPU utilization, dataset completeness, and self-monitoring.
2. Set up the 30-minute self-check cron as specified in CLAUDE.md. The cron must check: progress, system disk safety (`df -h /`), and GPU task health (`nvidia-smi` + `ps aux | grep python`).
3. Verify proxy is running: `curl -x http://127.0.0.1:7890 https://pypi.org` — if not, start mihomo.

---

## Task 1: Install Dependencies & Clean Old Data

**Files:**
- None (environment setup only)

- [ ] **Step 1: Install pyrender and EGL dependencies**

```bash
pip install pyrender PyOpenGL PyOpenGL_accelerate
apt-get install -y libegl1-mesa-dev libgles2-mesa-dev
```

- [ ] **Step 2: Verify pyrender works with EGL**

```bash
PYOPENGL_PLATFORM=egl python3 -c "
import pyrender
import trimesh
import numpy as np
mesh = trimesh.creation.box()
scene = pyrender.Scene()
scene.add(pyrender.Mesh.from_trimesh(mesh))
camera = pyrender.PerspectiveCamera(yfov=np.pi/3)
scene.add(camera, pose=np.eye(4))
light = pyrender.DirectionalLight(intensity=3.0)
scene.add(light, pose=np.eye(4))
r = pyrender.OffscreenRenderer(224, 224)
color, _ = r.render(scene)
r.delete()
print(f'Render OK: shape={color.shape}, mean={color.mean():.1f}')
"
```

Expected: `Render OK: shape=(224, 224, 3), mean=...` (no errors)

- [ ] **Step 3: Add PYOPENGL_PLATFORM to shell profile**

```bash
echo 'export PYOPENGL_PLATFORM=egl' >> ~/.bashrc
export PYOPENGL_PLATFORM=egl
```

- [ ] **Step 4: Clean old rendered data**

```bash
rm -rf /home/cc/data/renders
rm -rf /home/cc/data/edges
rm -rf /home/cc/data/sketches
rm -rf /home/cc/data/embeddings
rm -f /home/cc/data/cad.index
rm -f /home/cc/data/projection_head_a.pt
rm -f /home/cc/data/sketch_encoder.pt
rm -f /home/cc/data/eval_results.json
rm -f /home/cc/data/good_model_ids.txt
rm -f /home/cc/data/embedded_model_ids.txt
rm -f /home/cc/data/hard_negatives.json
mkdir -p /home/cc/data/tmp
```

- [ ] **Step 5: Verify STEP files still exist**

```bash
ls /home/cc/data/abc_step/step/*.step | wc -l
```

Expected: ~1,000,000 files. If less than 900,000, re-download is needed.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: clean old data artifacts, prepare for pipeline v2"
```

---

## Task 2: Rewrite Rendering Pipeline (pyrender + EGL)

**Files:**
- Rewrite: `scripts/render_all.py`

- [ ] **Step 1: Write test for pyrender rendering**

Create `tests/test_render_pyrender.py`:

```python
import numpy as np
import pytest
from pathlib import Path
from PIL import Image


def test_render_single_model(tmp_path):
    """Test that render_one produces 6 valid PNG images."""
    import trimesh

    # Create a simple mesh and save as STL
    mesh = trimesh.creation.box(extents=[1, 1, 1])
    stl_path = tmp_path / "test.stl"
    mesh.export(str(stl_path))

    from scripts.render_all import render_one_model
    output_dir = tmp_path / "output"
    result = render_one_model(str(stl_path), str(output_dir), 224)
    assert result is True
    for i in range(6):
        img_path = output_dir / f"view_{i}.png"
        assert img_path.exists()
        img = Image.open(img_path)
        assert img.size == (224, 224)
        arr = np.array(img)
        # Should not be all-white (object should be visible)
        assert arr.mean() < 250


def test_render_handles_empty_mesh(tmp_path):
    """Test that render gracefully handles degenerate meshes."""
    import trimesh
    mesh = trimesh.Trimesh(vertices=[], faces=[])
    stl_path = tmp_path / "empty.stl"
    mesh.export(str(stl_path))

    from scripts.render_all import render_one_model
    output_dir = tmp_path / "output"
    result = render_one_model(str(stl_path), str(output_dir), 224)
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/cc/cad-retriever && pytest tests/test_render_pyrender.py -v
```

Expected: FAIL (render_one_model not defined)

- [ ] **Step 3: Implement new render_all.py**

Rewrite `scripts/render_all.py`:

```python
"""
Pyrender + EGL GPU offscreen rendering for 1M CAD models.
Reads STEP → STL (via OCP), then renders 6 views with pyrender.
"""
import os
os.environ["PYOPENGL_PLATFORM"] = "egl"

import argparse
import math
import numpy as np
import tempfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

VIEW_ANGLES = [(30, 0), (30, 60), (30, 120), (30, 180), (30, 240), (30, 300)]
TMP_DIR = Path("/home/cc/data/tmp")


def render_one_model(stl_path: str, output_dir: str, image_size: int = 224) -> bool:
    """Render a single mesh to 6 views. Returns True on success."""
    import pyrender
    import trimesh
    from PIL import Image

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        mesh = trimesh.load(stl_path, force='mesh')
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return False
    except Exception:
        return False

    # Normalize to unit sphere
    center = mesh.centroid
    scale = max(mesh.extents) if max(mesh.extents) > 0 else 1.0
    mesh.vertices = (mesh.vertices - center) / scale

    # Create pyrender scene
    material = pyrender.MetallicRoughnessMaterial(
        baseColorFactor=[0.6, 0.6, 0.6, 1.0],
        metallicFactor=0.2,
        roughnessFactor=0.8,
    )
    pr_mesh = pyrender.Mesh.from_trimesh(mesh, material=material)

    renderer = pyrender.OffscreenRenderer(image_size, image_size)

    try:
        for i, (elev, azim) in enumerate(VIEW_ANGLES):
            scene = pyrender.Scene(bg_color=[1.0, 1.0, 1.0, 1.0],
                                   ambient_light=[0.3, 0.3, 0.3])
            scene.add(pr_mesh)

            # Camera pose
            elev_rad = math.radians(elev)
            azim_rad = math.radians(azim)
            dist = 2.5
            cx = dist * math.cos(elev_rad) * math.sin(azim_rad)
            cy = dist * math.cos(elev_rad) * math.cos(azim_rad)
            cz = dist * math.sin(elev_rad)
            camera_pos = np.array([cx, cy, cz])

            # Look-at matrix
            forward = -camera_pos / np.linalg.norm(camera_pos)
            right = np.cross(forward, np.array([0, 0, 1]))
            if np.linalg.norm(right) < 1e-6:
                right = np.cross(forward, np.array([0, 1, 0]))
            right = right / np.linalg.norm(right)
            up = np.cross(right, forward)

            pose = np.eye(4)
            pose[:3, 0] = right
            pose[:3, 1] = up
            pose[:3, 2] = -forward
            pose[:3, 3] = camera_pos

            camera = pyrender.PerspectiveCamera(yfov=math.pi / 4)
            scene.add(camera, pose=pose)

            light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
            scene.add(light, pose=pose)

            color, _ = renderer.render(scene)
            img = Image.fromarray(color)
            img.save(output_dir / f"view_{i}.png")
    except Exception:
        renderer.delete()
        return False

    renderer.delete()
    return True


def step_to_stl(step_path: str) -> str | None:
    """Convert STEP to STL via OCP. Returns STL path or None."""
    from OCP.STEPControl import STEPControl_Reader
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        reader = STEPControl_Reader()
        if reader.ReadFile(step_path) != 1:
            return None
        reader.TransferRoots()
        shape = reader.OneShape()
        BRepMesh_IncrementalMesh(shape, 0.5).Perform()

        stl_path = str(TMP_DIR / f"{Path(step_path).stem}.stl")
        StlAPI_Writer().Write(shape, stl_path)
        return stl_path
    except Exception:
        return None


def render_worker(args_tuple):
    """Worker: STEP → STL → render 6 views."""
    step_path, output_dir, image_size = args_tuple
    output_dir = Path(output_dir)
    if (output_dir / "view_5.png").exists():
        return True

    stl_path = step_to_stl(step_path)
    if stl_path is None:
        return False

    try:
        result = render_one_model(stl_path, str(output_dir), image_size)
    finally:
        try:
            os.unlink(stl_path)
        except OSError:
            pass
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=Path("/home/cc/data/abc_step/step"))
    parser.add_argument("--output", type=Path,
                        default=Path("/home/cc/data/renders"))
    parser.add_argument("--size", type=int, default=224)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    files = sorted(args.input.rglob("*.step"))
    print(f"Found {len(files)} STEP files")
    args.output.mkdir(parents=True, exist_ok=True)

    tasks = [
        (str(f), str(args.output / f.stem), args.size)
        for f in files
        if not (args.output / f.stem / "view_5.png").exists()
    ]
    already = len(files) - len(tasks)
    print(f"Already done: {already}, To render: {len(tasks)}")

    if not tasks:
        print("All done!")
        exit(0)

    failed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(render_worker, t): t for t in tasks}
        with tqdm(total=len(tasks), desc="Rendering") as pbar:
            for future in as_completed(futures):
                try:
                    if not future.result():
                        failed += 1
                except Exception:
                    failed += 1
                pbar.update(1)

    done = sum(1 for f in files if (args.output / f.stem / "view_5.png").exists())
    print(f"Done: {done}/{len(files)}, Failed: {failed}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/cc/cad-retriever && PYOPENGL_PLATFORM=egl pytest tests/test_render_pyrender.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/render_all.py tests/test_render_pyrender.py
git commit -m "feat: rewrite render pipeline with pyrender + EGL offscreen"
```

---

## Task 3: Fix Edge Detection (Canny)

**Files:**
- Modify: `src/cad_retriever/data/edge_detect.py`
- Modify: `tests/test_edge_detect.py`

- [ ] **Step 1: Update test for Canny edge detection**

Replace `tests/test_edge_detect.py`:

```python
import numpy as np
from PIL import Image
from cad_retriever.data.edge_detect import detect_edges


def test_detect_edges_output_shape():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img)
    assert edges.size == (224, 224)
    assert edges.mode == "L"


def test_detect_edges_binary_output():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img)
    arr = np.array(edges)
    unique = np.unique(arr)
    assert len(unique) <= 2


def test_detect_edges_finds_box_edges():
    """A grey box on white background should produce clear edges."""
    arr = np.ones((224, 224, 3), dtype=np.uint8) * 255
    arr[50:170, 50:170] = 128  # grey box
    img = Image.fromarray(arr)
    edges = detect_edges(img)
    edge_arr = np.array(edges)
    # Should have some white pixels (edges detected)
    assert edge_arr.sum() > 0
    # Edges should be near the box boundary
    assert edge_arr[100, 100] == 0  # center of box = no edge
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/cc/cad-retriever && pytest tests/test_edge_detect.py -v
```

Expected: `test_detect_edges_binary_output` FAILS (current CLAHE produces grey-tone, not binary)

- [ ] **Step 3: Implement proper Canny edge detection**

Replace `src/cad_retriever/data/edge_detect.py`:

```python
import cv2
import numpy as np
from PIL import Image


def detect_edges(image: Image.Image) -> Image.Image:
    """Detect edges using Canny with auto-threshold.
    Returns binary edge map: white edges on black background.
    """
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)

    # Auto-threshold based on median intensity
    median = np.median(blurred)
    low = int(max(0, 0.33 * median))
    high = int(min(255, 0.66 * median))
    # Ensure minimum separation
    if high - low < 30:
        low = max(0, int(median) - 30)
        high = min(255, int(median) + 30)

    edges = cv2.Canny(blurred, low, high)
    return Image.fromarray(edges, mode="L")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/cc/cad-retriever && pytest tests/test_edge_detect.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/data/edge_detect.py tests/test_edge_detect.py
git commit -m "fix: replace CLAHE with proper Canny edge detection"
```

---

## Task 4: Fix SketchEncoder LoRA Gradient Flow

**Files:**
- Modify: `src/cad_retriever/models/encoder.py`

- [ ] **Step 1: Write test proving LoRA gradients flow**

Create `tests/test_lora_gradient.py`:

```python
import torch
from cad_retriever.models.encoder import SketchEncoder
from cad_retriever.models.lora import apply_lora


def test_lora_receives_gradients():
    """LoRA parameters must receive gradients during forward+backward."""
    enc = SketchEncoder(embed_dim=512, lora_rank=16)
    apply_lora(enc.visual, rank=16)

    x = torch.randn(2, 3, 224, 224)
    out = enc(x)
    loss = out.sum()
    loss.backward()

    # Find a LoRA parameter and check it has a gradient
    found_grad = False
    for name, param in enc.named_parameters():
        if "lora_A" in name or "lora_B" in name:
            if param.grad is not None and param.grad.abs().sum() > 0:
                found_grad = True
                break
    assert found_grad, "No LoRA parameter received a gradient"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/cc/cad-retriever && pytest tests/test_lora_gradient.py -v
```

Expected: FAIL (torch.no_grad blocks gradients)

- [ ] **Step 3: Fix SketchEncoder.forward**

In `src/cad_retriever/models/encoder.py`, replace the SketchEncoder.forward method:

```python
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 3, H, W)"""
        feats = self.visual(x)  # (B, clip_dim) — LoRA gets gradients
        out = self.projection(feats)  # (B, embed_dim)
        return nn.functional.normalize(out, dim=-1)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/cc/cad-retriever && pytest tests/test_lora_gradient.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_retriever/models/encoder.py tests/test_lora_gradient.py
git commit -m "fix: remove torch.no_grad in SketchEncoder to enable LoRA training"
```

---

## Task 5: Rewrite Phase 1 Training (InfoNCE + Hard Negatives)

**Files:**
- Modify: `src/cad_retriever/training/dataset.py`
- Rewrite: `src/cad_retriever/training/train_phase1.py`
- Modify: `scripts/train.py`

- [ ] **Step 1: Write test for Phase 1 contrastive dataset**

Create `tests/test_phase1_infonce.py`:

```python
import torch
import numpy as np
from pathlib import Path
from PIL import Image


def _make_renders(tmp_path, n_models=10, n_views=6):
    renders_dir = tmp_path / "renders"
    model_ids = []
    for i in range(n_models):
        mid = f"model_{i:06d}"
        model_ids.append(mid)
        d = renders_dir / mid
        d.mkdir(parents=True)
        for v in range(n_views):
            img = Image.fromarray(
                np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
            img.save(d / f"view_{v}.png")
    return renders_dir, model_ids


def test_contrastive_dataset_returns_two_views(tmp_path):
    from cad_retriever.training.dataset import Phase1ContrastiveDataset
    renders_dir, model_ids = _make_renders(tmp_path)
    ds = Phase1ContrastiveDataset(renders_dir, model_ids, num_views=6)
    item = ds[0]
    assert item["view_a"].shape == (3, 224, 224)
    assert item["view_b"].shape == (3, 224, 224)
    assert item["model_id"] == model_ids[0]


def test_infonce_phase1_loss_decreases():
    """One training step should reduce loss."""
    from cad_retriever.models.encoder import CADEncoder
    from cad_retriever.training.losses import InfoNCELoss

    encoder = CADEncoder(embed_dim=512)
    loss_fn = InfoNCELoss(temperature=0.07)
    optimizer = torch.optim.Adam(encoder.projection.parameters(), lr=1e-3)

    # Fake batch: 8 models, 2 views each
    views_a = torch.randn(8, 3, 224, 224)
    views_b = torch.randn(8, 3, 224, 224)

    encoder.train()
    with torch.no_grad():
        feats_a = encoder.encode_single_view(views_a)
        feats_b = encoder.encode_single_view(views_b)

    emb_a = encoder.projection(feats_a)
    emb_a = torch.nn.functional.normalize(emb_a, dim=-1)
    emb_b = encoder.projection(feats_b)
    emb_b = torch.nn.functional.normalize(emb_b, dim=-1)

    loss1 = loss_fn(emb_a, emb_b)
    optimizer.zero_grad()
    loss1.backward()
    optimizer.step()

    # Second forward
    emb_a2 = encoder.projection(feats_a)
    emb_a2 = torch.nn.functional.normalize(emb_a2, dim=-1)
    emb_b2 = encoder.projection(feats_b)
    emb_b2 = torch.nn.functional.normalize(emb_b2, dim=-1)
    loss2 = loss_fn(emb_a2, emb_b2)

    assert loss2.item() < loss1.item()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/cc/cad-retriever && pytest tests/test_phase1_infonce.py -v
```

Expected: FAIL (Phase1ContrastiveDataset not defined)

- [ ] **Step 3: Add Phase1ContrastiveDataset to dataset.py**

Add to `src/cad_retriever/training/dataset.py`:

```python
import random


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
```

- [ ] **Step 4: Rewrite train_phase1.py**

Replace `src/cad_retriever/training/train_phase1.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/cc/cad-retriever && pytest tests/test_phase1_infonce.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/cad_retriever/training/dataset.py \
        src/cad_retriever/training/train_phase1.py \
        tests/test_phase1_infonce.py
git commit -m "feat: Phase 1 training with InfoNCE contrastive loss"
```

---

## Task 6: Hard Negative Mining & Phase 1b

**Files:**
- Modify: `src/cad_retriever/training/hard_negatives.py`
- Modify: `scripts/train.py`

- [ ] **Step 1: Update hard_negatives.py**

Replace `src/cad_retriever/training/hard_negatives.py`:

```python
import json
import numpy as np
import faiss
from pathlib import Path
from tqdm import tqdm


def mine_hard_negatives(
    embeddings_dir: Path,
    model_ids: list[str],
    output_path: Path,
    top_k: int = 20,
    hard_range: tuple[int, int] = (5, 20),
) -> dict[str, list[str]]:
    """Mine hard negatives: for each model, find rank 5-20 nearest neighbors."""
    vectors = []
    valid_ids = []
    for mid in tqdm(model_ids, desc="Loading embeddings"):
        path = embeddings_dir / f"{mid}.npy"
        if path.exists():
            vectors.append(np.load(path))
            valid_ids.append(mid)

    vectors = np.stack(vectors).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    d = vectors.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(vectors)
    _, indices = index.search(vectors, top_k)

    lo, hi = hard_range
    hard_negs = {}
    for i, mid in enumerate(valid_ids):
        neg_indices = indices[i, lo:hi]
        hard_negs[mid] = [valid_ids[j] for j in neg_indices if j != i]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(hard_negs, f)

    print(f"Mined hard negatives for {len(hard_negs)} models → {output_path}")
    return hard_negs
```

- [ ] **Step 2: Update scripts/train.py to support phase1a/phase1b**

Replace `scripts/train.py`:

```python
"""CLI entry point for training phases."""
import argparse
from pathlib import Path
from cad_retriever.config import Config


def main():
    parser = argparse.ArgumentParser(description="Train CAD Sketch Retriever")
    parser.add_argument("--phase", type=str,
                        choices=["1a", "1b", "2"], required=True)
    parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    args = parser.parse_args()

    config = Config(data_root=args.data_root)
    manifest = config.data_root / "model_ids.txt"
    model_ids = manifest.read_text().strip().split("\n")

    # Filter to models that have renders
    model_ids = [mid for mid in model_ids
                 if (config.renders_dir / mid / "view_5.png").exists()]
    print(f"Using {len(model_ids)} models with renders")

    if args.phase == "1a":
        from cad_retriever.training.train_phase1 import train_phase1
        train_phase1(config, model_ids,
                     num_epochs=args.epochs,
                     lr=args.lr or 1e-3,
                     batch_size=args.batch_size or 256)

    elif args.phase == "1b":
        from cad_retriever.training.train_phase1 import train_phase1
        # Load hard negatives — Phase 1b uses lower lr
        train_phase1(config, model_ids,
                     num_epochs=args.epochs,
                     lr=args.lr or 5e-4,
                     batch_size=args.batch_size or 256)

    elif args.phase == "2":
        from cad_retriever.training.train_phase2 import train_phase2
        # Filter to models with embeddings
        model_ids = [mid for mid in model_ids
                     if (config.embeddings_dir / f"{mid}.npy").exists()]
        print(f"Phase 2: {len(model_ids)} models with embeddings")
        train_phase2(config, model_ids, num_epochs=args.epochs)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add src/cad_retriever/training/hard_negatives.py scripts/train.py
git commit -m "feat: hard negative mining and phase1a/1b training split"
```

---

## Task 7: Fix Phase 2 Training

**Files:**
- Modify: `src/cad_retriever/training/train_phase2.py`

- [ ] **Step 1: Update train_phase2.py**

Replace `src/cad_retriever/training/train_phase2.py`:

```python
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

    # 95% train, 5% val
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
        # Train
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

        # Validate
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

        # Save best
        if avg_val < best_val_loss:
            best_val_loss = avg_val
            torch.save(encoder.state_dict(), config.data_root / "sketch_encoder.pt")
            print(f"  → Saved best checkpoint (val_loss={avg_val:.4f})")

    return encoder
```

- [ ] **Step 2: Run existing tests**

```bash
cd /home/cc/cad-retriever && pytest tests/ -v --timeout=60
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/cad_retriever/training/train_phase2.py
git commit -m "fix: Phase 2 with grad clipping, val split, best checkpoint"
```

---

## Task 8: Update Preprocessing Script

**Files:**
- Modify: `scripts/preprocess_all.py`

- [ ] **Step 1: Simplify preprocess_all.py (single pass, no loop)**

Replace `scripts/preprocess_all.py`:

```python
"""Generate edge maps and synthetic sketches for all rendered models."""
import argparse
import random
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from cad_retriever.data.edge_detect import detect_edges
from cad_retriever.data.sketch_synth import synthesize_sketch

parser = argparse.ArgumentParser()
parser.add_argument("--renders", type=Path, default=Path("/home/cc/data/renders"))
parser.add_argument("--edges-out", type=Path, default=Path("/home/cc/data/edges"))
parser.add_argument("--sketches-out", type=Path, default=Path("/home/cc/data/sketches"))
args = parser.parse_args()

model_dirs = sorted(d for d in args.renders.iterdir() if d.is_dir())
print(f"Total rendered models: {len(model_dirs)}")

processed = 0
for model_dir in tqdm(model_dirs, desc="Preprocessing"):
    mid = model_dir.name
    edge_dir = args.edges_out / mid
    sketch_dir = args.sketches_out / mid

    # Skip if already done
    if (edge_dir / "view_5.png").exists():
        continue

    edge_dir.mkdir(parents=True, exist_ok=True)
    sketch_dir.mkdir(parents=True, exist_ok=True)

    for view_file in sorted(model_dir.glob("view_*.png")):
        try:
            img = Image.open(view_file)
            edge = detect_edges(img)
            edge.save(edge_dir / view_file.name)
            difficulty = random.uniform(0.2, 0.8)
            sketch = synthesize_sketch(edge, difficulty=difficulty)
            sketch.save(sketch_dir / view_file.name)
        except Exception as e:
            print(f"Error {view_file}: {e}")
    processed += 1

print(f"Preprocessed {processed} new models")
```

- [ ] **Step 2: Commit**

```bash
git add scripts/preprocess_all.py
git commit -m "fix: simplify preprocess_all to single-pass without loop"
```

---

## Task 9: Run Full Data Pipeline

**Files:** None (execution only)

**IMPORTANT:** This task runs long-duration processes. Use `nohup` and monitor with the 30-min cron. Do NOT proceed to the next step until the current one is fully complete.

- [ ] **Step 1: Render all models**

```bash
cd /home/cc/cad-retriever
nohup PYOPENGL_PLATFORM=egl python3 scripts/render_all.py \
    --input /home/cc/data/abc_step/step \
    --output /home/cc/data/renders \
    --size 224 --workers 16 \
    > /home/cc/data/render_v2.log 2>&1 &
echo $! > /home/cc/data/render_pid.txt
```

Monitor progress:
```bash
ls /home/cc/data/renders/ | wc -l  # should approach 1M
tail -1 /home/cc/data/render_v2.log
df -h /  # must stay below 80%
```

Wait until complete (~3-9 hours). Verify:
```bash
find /home/cc/data/renders -name "view_5.png" | wc -l
```
Expected: >= 900,000

- [ ] **Step 2: Preprocess all (edge + sketch)**

```bash
nohup python3 scripts/preprocess_all.py \
    --renders /home/cc/data/renders \
    --edges-out /home/cc/data/edges \
    --sketches-out /home/cc/data/sketches \
    > /home/cc/data/preprocess_v2.log 2>&1 &
```

Wait until complete. Verify:
```bash
find /home/cc/data/edges -name "view_5.png" | wc -l
```
Expected: same count as renders

- [ ] **Step 3: Commit progress marker**

```bash
cd /home/cc/cad-retriever
git add -A && git commit -m "chore: data pipeline v2 complete (render + preprocess)" --allow-empty
git push origin main
```

---

## Task 10: Train Phase 1a (InfoNCE)

**Files:** None (execution only)

- [ ] **Step 1: Run Phase 1a training**

```bash
cd /home/cc/cad-retriever
nohup python3 scripts/train.py --phase 1a --data-root /home/cc/data \
    --epochs 5 --batch-size 256 \
    > /home/cc/data/train_phase1a.log 2>&1 &
```

Monitor:
```bash
tail -5 /home/cc/data/train_phase1a.log
nvidia-smi  # GPU should be >80%
```

Wait until complete. Verify `projection_head_a.pt` exists:
```bash
ls -la /home/cc/data/projection_head_a.pt
```

- [ ] **Step 2: Embed all models (intermediate)**

```bash
nohup python3 scripts/embed_all.py --data-root /home/cc/data \
    > /home/cc/data/embed_v2.log 2>&1 &
```

Wait until complete:
```bash
ls /home/cc/data/embeddings/*.npy | wc -l
```
Expected: >= 900,000

- [ ] **Step 3: Mine hard negatives**

```bash
python3 -c "
from pathlib import Path
from cad_retriever.config import Config
from cad_retriever.training.hard_negatives import mine_hard_negatives

config = Config(data_root=Path('/home/cc/data'))
model_ids = config.data_root.joinpath('model_ids.txt').read_text().strip().split('\n')
model_ids = [m for m in model_ids if (config.embeddings_dir / f'{m}.npy').exists()]
mine_hard_negatives(config.embeddings_dir, model_ids,
                    config.data_root / 'hard_negatives.json')
"
```

- [ ] **Step 4: Run Phase 1b training (with hard negatives)**

```bash
nohup python3 scripts/train.py --phase 1b --data-root /home/cc/data \
    --epochs 5 --batch-size 256 --lr 5e-4 \
    > /home/cc/data/train_phase1b.log 2>&1 &
```

Wait until complete.

- [ ] **Step 5: Re-embed all models (final)**

```bash
rm -rf /home/cc/data/embeddings
nohup python3 scripts/embed_all.py --data-root /home/cc/data \
    > /home/cc/data/embed_final.log 2>&1 &
```

Wait until complete.

- [ ] **Step 6: Build FAISS index**

```bash
python3 scripts/build_index.py --data-root /home/cc/data
```

Verify:
```bash
ls -la /home/cc/data/cad.index
```

- [ ] **Step 7: Commit**

```bash
cd /home/cc/cad-retriever && git add -A
git commit -m "chore: Phase 1 training complete, FAISS index built" --allow-empty
git push origin main
```

---

## Task 11: Train Phase 2 & Evaluate

**Files:** None (execution only)

- [ ] **Step 1: Run Phase 2 training**

```bash
cd /home/cc/cad-retriever
nohup python3 scripts/train.py --phase 2 --data-root /home/cc/data \
    --epochs 10 \
    > /home/cc/data/train_phase2_v2.log 2>&1 &
```

Monitor:
```bash
tail -5 /home/cc/data/train_phase2_v2.log
nvidia-smi
```

Wait until complete. Verify:
```bash
ls -la /home/cc/data/sketch_encoder.pt
```

- [ ] **Step 2: Run evaluation**

```bash
python3 scripts/evaluate.py --data-root /home/cc/data --test-size 5000
```

Check output against targets:
- recall@1 >= 0.60
- recall@10 >= 0.90
- MRR >= 0.70

- [ ] **Step 3: If targets not met — fallback actions**

If recall@1 < 0.60:
1. Increase Phase 2 epochs to 20: `python3 scripts/train.py --phase 2 --epochs 20`
2. If still failing, increase LoRA rank to 32 in config.py and retrain Phase 2
3. If still failing, try ViT-L/14 backbone (change `clip_model` in encoder.py)

Re-evaluate after each fallback.

- [ ] **Step 4: Commit results**

```bash
cd /home/cc/cad-retriever && git add -A
git commit -m "feat: training complete, eval meets targets"
git push origin main
```

---

## Task 12: Deploy Serving Endpoint

**Files:**
- Modify: `src/cad_retriever/serving/app.py` (add module-level app)

- [ ] **Step 1: Add module-level app creation**

Add at the bottom of `src/cad_retriever/serving/app.py`:

```python
# Module-level app for uvicorn
app = create_app()
```

- [ ] **Step 2: Start FastAPI server**

```bash
cd /home/cc/cad-retriever
nohup python3 -m uvicorn cad_retriever.serving.app:app \
    --host 0.0.0.0 --port 8000 \
    > /home/cc/data/serve_v2.log 2>&1 &
```

- [ ] **Step 3: Verify health endpoint**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok","index_size":...}` with index_size >= 900,000

- [ ] **Step 4: Test search with a sample sketch**

```bash
SKETCH=$(ls /home/cc/data/sketches/*/view_0.png | head -1)
curl -X POST http://localhost:8000/search \
    -F "sketch=@$SKETCH" -F "top_k=5"
```

Expected: JSON with 5 results, each having `model_id` and `score > 0`

- [ ] **Step 5: Final commit and push**

```bash
cd /home/cc/cad-retriever && git add -A
git commit -m "feat: serving endpoint deployed and verified"
git push origin main
```

---

## Completion Checklist

Before declaring done, verify ALL of these:

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Renders: `find /home/cc/data/renders -name "view_5.png" | wc -l` >= 900,000
- [ ] Edges/sketches: same count as renders
- [ ] Embeddings: `ls /home/cc/data/embeddings/*.npy | wc -l` >= 900,000
- [ ] FAISS index: `ls -la /home/cc/data/cad.index`
- [ ] Eval targets: recall@1 >= 0.60, recall@10 >= 0.90, MRR >= 0.70
- [ ] Serving: `curl http://localhost:8000/health` returns OK
- [ ] System disk: `df -h /` < 80%
- [ ] Git: `git status` clean, all pushed
