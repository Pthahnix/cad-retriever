# ABC Download + Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pipeline's first two stages — download the 1M ABC STEP dataset and probe each model's cheap topology metrics — landing results in a LanceDB manifest table that serves all downstream stages.

**Architecture:** Three decoupled units (download → ingest → probe) communicating through a single LanceDB manifest table. STEP bytes stay on the filesystem; the manifest is a thin metadata/pointer layer. Probe uses OCC topology traversal only (no meshing) to predict mesh-stage blowups, with many parallel workers feeding a single serial Lance writer to avoid version conflicts.

**Tech Stack:** Python 3.12, OCP (OpenCASCADE via cadquery), py7zr, lancedb, pyarrow, duckdb (reporting), pytest.

**Reference spec:** `docs/superpowers/specs/2026-06-11-download-probe-design.md`

**Where this runs:** AutoDL pod. Data root `/home/cc/data` (2TB). All internet via proxy `http://127.0.0.1:7890`. Python `/root/miniconda3/bin/python3`. NEVER write data under the repo or `/tmp/`.

---

## File Structure

New package laid out fresh at repo root (the previous tree is archived under `context/history/`).

- Create: `pyproject.toml` — package + deps (lancedb, py7zr, pyarrow, duckdb, pytest).
- Create: `src/cad_pipeline/__init__.py`
- Create: `src/cad_pipeline/config.py` — paths + probe thresholds (config, NOT hardcoded).
- Create: `src/cad_pipeline/manifest.py` — LanceDB schema, open/create table, single-writer commit helper, status queries.
- Create: `src/cad_pipeline/download.py` — port of the proven downloader (7z header check, retries, resume, extract).
- Create: `src/cad_pipeline/ingest.py` — scan extracted `.step`, register one manifest row each (source adapter boundary).
- Create: `src/cad_pipeline/probe.py` — topology probe (no mesh) + flag judgment; parallel workers + serial writer.
- Create: `src/cad_pipeline/report.py` — histogram + flag-count summary via DuckDB over the manifest.
- Create: `scripts/run_download.py`, `scripts/run_ingest.py`, `scripts/run_probe.py`, `scripts/run_report.py` — thin CLI entrypoints.
- Test: `tests/conftest.py`, `tests/test_manifest.py`, `tests/test_ingest.py`, `tests/test_probe.py`, `tests/test_download.py`.

Each unit is independently runnable and restartable. They share only the manifest table.

---

## Task 1: Project scaffold + config

**Files:**
- Create: `pyproject.toml`
- Create: `src/cad_pipeline/__init__.py`
- Create: `src/cad_pipeline/config.py`
- Test: `tests/test_config.py`, `tests/conftest.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "cad-pipeline"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "lancedb>=0.15",
    "pyarrow>=15",
    "py7zr>=0.21",
    "duckdb>=1.0",
    "tqdm>=4.66",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/cad_pipeline"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Note: OCP is provided by the pod's cadquery install, not declared here.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_config.py
from cad_pipeline.config import Config

def test_config_defaults(tmp_path):
    cfg = Config(data_root=tmp_path)
    assert cfg.data_root == tmp_path
    assert cfg.manifest_path == tmp_path / "manifest.lance"
    assert cfg.step_dir == tmp_path / "abc_step" / "step"
    # thresholds are config, not magic numbers
    assert cfg.max_file_size_mb == 50.0
    assert cfg.max_n_faces == 5000
    assert cfg.min_n_faces == 3
    assert cfg.max_bbox_ratio == 1000.0
    assert cfg.proxy == "http://127.0.0.1:7890"
```

```python
# tests/conftest.py
import pytest
from cad_pipeline.config import Config

@pytest.fixture
def config(tmp_path):
    return Config(data_root=tmp_path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: cad_pipeline.config`

- [ ] **Step 4: Write `config.py`**

```python
# src/cad_pipeline/config.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    data_root: Path = Path("/home/cc/data")
    proxy: str = "http://127.0.0.1:7890"

    # probe thresholds — TEMPORARY starting points, refined from the
    # first probe run's real histogram (see spec section 5). Do NOT
    # treat these as final; they are config exactly so they can change.
    max_file_size_mb: float = 50.0   # > -> flag "oversized" (non-fatal signal)
    max_n_faces: int = 5000          # > -> flag "too_complex"
    min_n_faces: int = 3             # < -> flag "too_simple"
    max_bbox_ratio: float = 1000.0   # > -> flag "degenerate"
    min_file_size_bytes: int = 1000  # < -> flag "corrupt"

    @property
    def manifest_path(self) -> Path:
        return self.data_root / "manifest.lance"

    @property
    def abc_dir(self) -> Path:
        return self.data_root / "abc_step"

    @property
    def chunks_dir(self) -> Path:
        return self.abc_dir / "chunks"

    @property
    def step_dir(self) -> Path:
        return self.abc_dir / "step"
```

```python
# src/cad_pipeline/__init__.py
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/cad_pipeline tests/test_config.py tests/conftest.py
git commit -m "feat: scaffold cad_pipeline package with config (probe thresholds as config)"
```

---

## Task 2: Manifest schema + LanceDB table

**Files:**
- Create: `src/cad_pipeline/manifest.py`
- Test: `tests/test_manifest.py`

The manifest is the single source of truth. All columns (including downstream-stage
placeholders and the vector column) are created now so no schema migration is needed later.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_manifest.py
import pyarrow as pa
from cad_pipeline.manifest import MANIFEST_SCHEMA, open_or_create, new_row

def test_schema_has_all_columns():
    names = set(MANIFEST_SCHEMA.names)
    assert {"model_id", "source", "src_path", "format", "file_size_mb"} <= names
    assert {"probe_n_faces", "probe_n_solids", "probe_n_edges",
            "probe_bbox_dims", "probe_bbox_ratio", "probe_status",
            "probe_error", "quality_flags", "render_eligible"} <= names
    # downstream placeholders incl. vector column
    assert {"render_status", "sketch_status", "caption_status", "embedding"} <= names

def test_new_row_defaults():
    row = new_row("abc/00000123", "abc", "/data/abc_step/step/00000123.step", 2.5)
    assert row["model_id"] == "abc/00000123"
    assert row["source"] == "abc"
    assert row["probe_status"] == "pending"
    assert row["render_status"] == "pending"
    assert row["quality_flags"] == []
    assert row["probe_n_faces"] is None

def test_open_or_create_roundtrip(tmp_path):
    tbl = open_or_create(tmp_path / "manifest.lance")
    tbl.add([new_row("abc/1", "abc", "/x/1.step", 1.0)])
    assert tbl.count_rows() == 1
    # reopening the same path returns the existing table, not a fresh one
    tbl2 = open_or_create(tmp_path / "manifest.lance")
    assert tbl2.count_rows() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: cad_pipeline.manifest`

- [ ] **Step 3: Write `manifest.py`**

```python
# src/cad_pipeline/manifest.py
from pathlib import Path
import pyarrow as pa
import lancedb

EMBED_DIM = 512  # CLIP projection dim (downstream); column built now, filled later

MANIFEST_SCHEMA = pa.schema([
    # identity / source (ingest fills)
    ("model_id", pa.string()),
    ("source", pa.string()),
    ("src_path", pa.string()),
    ("format", pa.string()),
    ("file_size_mb", pa.float64()),
    # topology probe (probe fills, no mesh)
    ("probe_n_faces", pa.int64()),
    ("probe_n_solids", pa.int64()),
    ("probe_n_edges", pa.int64()),
    ("probe_bbox_dims", pa.list_(pa.float64())),
    ("probe_bbox_ratio", pa.float64()),
    ("probe_status", pa.string()),
    ("probe_error", pa.string()),
    # judgment (probe fills)
    ("quality_flags", pa.list_(pa.string())),
    ("render_eligible", pa.bool_()),
    # downstream placeholders (null/pending this stage)
    ("render_status", pa.string()),
    ("sketch_status", pa.string()),
    ("caption_status", pa.string()),
    ("embedding", pa.list_(pa.float32(), EMBED_DIM)),
])

def new_row(model_id: str, source: str, src_path: str, file_size_mb: float) -> dict:
    return {
        "model_id": model_id, "source": source, "src_path": src_path,
        "format": "step", "file_size_mb": file_size_mb,
        "probe_n_faces": None, "probe_n_solids": None, "probe_n_edges": None,
        "probe_bbox_dims": None, "probe_bbox_ratio": None,
        "probe_status": "pending", "probe_error": None,
        "quality_flags": [], "render_eligible": None,
        "render_status": "pending", "sketch_status": "pending",
        "caption_status": "pending", "embedding": None,
    }

def open_or_create(manifest_path: Path):
    db = lancedb.connect(str(Path(manifest_path).parent))
    name = Path(manifest_path).stem
    if name in db.table_names():
        return db.open_table(name)
    return db.create_table(name, schema=MANIFEST_SCHEMA)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_pipeline/manifest.py tests/test_manifest.py
git commit -m "feat: LanceDB manifest schema with all-stage columns + vector placeholder"
```

---

## Task 3: Ingest — register extracted STEP files into the manifest

**Files:**
- Create: `src/cad_pipeline/ingest.py`
- Create: `scripts/run_ingest.py`
- Test: `tests/test_ingest.py`

Ingest only registers existence (path + size); it does NOT open file contents.
`ingest_source` is the adapter boundary — a new dataset = a new adapter that maps its
files to `(model_id, src_path)` and reuses `register_rows`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
from cad_pipeline.manifest import open_or_create
from cad_pipeline.ingest import abc_model_id, ingest_abc

def test_abc_model_id():
    # ABC stem like "00000123" -> "abc/00000123"
    assert abc_model_id("00000123") == "abc/00000123"

def test_ingest_abc_creates_rows(tmp_path):
    step_dir = tmp_path / "abc_step" / "step"
    step_dir.mkdir(parents=True)
    (step_dir / "00000001.step").write_bytes(b"x" * 2048)
    (step_dir / "00000002.step").write_bytes(b"y" * 4096)
    tbl = open_or_create(tmp_path / "manifest.lance")

    n = ingest_abc(step_dir, tbl)
    assert n == 2
    rows = {r["model_id"]: r for r in tbl.to_arrow().to_pylist()}
    assert set(rows) == {"abc/00000001", "abc/00000002"}
    r = rows["abc/00000001"]
    assert r["source"] == "abc"
    assert r["src_path"].endswith("00000001.step")
    assert r["format"] == "step"
    assert abs(r["file_size_mb"] - 2048 / 1_048_576) < 1e-6
    assert r["probe_status"] == "pending"

def test_ingest_abc_is_idempotent(tmp_path):
    step_dir = tmp_path / "abc_step" / "step"
    step_dir.mkdir(parents=True)
    (step_dir / "00000001.step").write_bytes(b"x" * 2048)
    tbl = open_or_create(tmp_path / "manifest.lance")
    ingest_abc(step_dir, tbl)
    added = ingest_abc(step_dir, tbl)  # rerun
    assert added == 0
    assert tbl.count_rows() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: cad_pipeline.ingest`

- [ ] **Step 3: Write `ingest.py`**

```python
# src/cad_pipeline/ingest.py
from pathlib import Path
from cad_pipeline.manifest import new_row

def abc_model_id(stem: str) -> str:
    return f"abc/{stem}"

def _existing_ids(tbl) -> set:
    if tbl.count_rows() == 0:
        return set()
    return set(tbl.to_arrow().column("model_id").to_pylist())

def register_rows(tbl, rows: list[dict]) -> int:
    """Append only rows whose model_id is not already present. Returns count added."""
    if not rows:
        return 0
    have = _existing_ids(tbl)
    fresh = [r for r in rows if r["model_id"] not in have]
    if fresh:
        tbl.add(fresh)
    return len(fresh)

def ingest_abc(step_dir: Path, tbl) -> int:
    """Adapter for the ABC source. Scans *.step, builds one row each."""
    rows = []
    for f in sorted(Path(step_dir).rglob("*.step")):
        size_mb = f.stat().st_size / 1_048_576
        rows.append(new_row(abc_model_id(f.stem), "abc", str(f.resolve()), size_mb))
    return register_rows(tbl, rows)
```

```python
# scripts/run_ingest.py
import argparse
from pathlib import Path
from cad_pipeline.config import Config
from cad_pipeline.manifest import open_or_create
from cad_pipeline.ingest import ingest_abc

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    args = ap.parse_args()
    cfg = Config(data_root=args.data_root)
    tbl = open_or_create(cfg.manifest_path)
    added = ingest_abc(cfg.step_dir, tbl)
    print(f"Ingested {added} new rows; manifest now {tbl.count_rows()} rows")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_pipeline/ingest.py scripts/run_ingest.py tests/test_ingest.py
git commit -m "feat: ingest adapter registers ABC STEP files into manifest (idempotent)"
```

---

## Task 4: Probe — flag judgment logic (pure, no OCC)

**Files:**
- Create: `src/cad_pipeline/probe.py` (judgment functions only this task)
- Test: `tests/test_probe.py`

Separate the pure judgment (metrics -> flags) from OCC reading so the threshold logic
is unit-testable without building STEP files. Fatal flags determine `render_eligible`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_probe.py
from cad_pipeline.config import Config
from cad_pipeline.probe import judge_flags, FATAL_FLAGS

def _cfg():
    return Config(data_root=".")

def test_clean_part_has_no_flags():
    flags = judge_flags(_cfg(), file_size_mb=2.0, n_faces=120,
                         n_solids=1, bbox_dims=[10, 20, 5])
    assert flags == []

def test_too_complex():
    flags = judge_flags(_cfg(), file_size_mb=2.0, n_faces=9000,
                        n_solids=1, bbox_dims=[10, 20, 5])
    assert "too_complex" in flags

def test_too_simple_and_oversized():
    flags = judge_flags(_cfg(), file_size_mb=80.0, n_faces=1,
                        n_solids=1, bbox_dims=[10, 20, 5])
    assert "too_simple" in flags
    assert "oversized" in flags

def test_no_solid():
    flags = judge_flags(_cfg(), file_size_mb=2.0, n_faces=50,
                        n_solids=0, bbox_dims=[10, 20, 5])
    assert "no_solid" in flags

def test_degenerate_flat_and_sliver():
    flat = judge_flags(_cfg(), file_size_mb=2.0, n_faces=50,
                       n_solids=1, bbox_dims=[10, 20, 0.0])
    assert "degenerate" in flat
    sliver = judge_flags(_cfg(), file_size_mb=2.0, n_faces=50,
                         n_solids=1, bbox_dims=[2000, 1, 1])
    assert "degenerate" in sliver

def test_corrupt_tiny_file():
    flags = judge_flags(_cfg(), file_size_mb=0.0005, n_faces=50,
                        n_solids=1, bbox_dims=[10, 20, 5])
    assert "corrupt" in flags

def test_render_eligible_only_when_no_fatal_flag():
    from cad_pipeline.probe import is_render_eligible
    assert is_render_eligible([]) is True
    assert is_render_eligible(["oversized"]) is True       # non-fatal
    assert is_render_eligible(["too_complex"]) is False
    assert is_render_eligible(["oversized", "no_solid"]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_probe.py -v`
Expected: FAIL with `ModuleNotFoundError: cad_pipeline.probe`

- [ ] **Step 3: Write the judgment part of `probe.py`**

```python
# src/cad_pipeline/probe.py
from cad_pipeline.config import Config

# fatal flags exclude a model from rendering; "oversized" is a non-fatal signal
FATAL_FLAGS = {"corrupt", "step_read_fail", "no_solid",
               "degenerate", "too_complex", "too_simple"}

def judge_flags(cfg: Config, file_size_mb: float, n_faces: int,
                n_solids: int, bbox_dims: list[float]) -> list[str]:
    """Map cheap metrics to quality flags. Pure function — no OCC, no I/O."""
    flags = []
    # aspect 1: metadata
    if file_size_mb * 1_048_576 < cfg.min_file_size_bytes:
        flags.append("corrupt")
    if file_size_mb > cfg.max_file_size_mb:
        flags.append("oversized")
    # aspect 2: topology
    if n_solids == 0:
        flags.append("no_solid")
    if n_faces > cfg.max_n_faces:
        flags.append("too_complex")
    if n_faces < cfg.min_n_faces:
        flags.append("too_simple")
    dims = [d for d in (bbox_dims or [])]
    if dims:
        mn, mx = min(dims), max(dims)
        if mn <= 1e-9:
            flags.append("degenerate")
        elif mx / mn > cfg.max_bbox_ratio:
            flags.append("degenerate")
    return flags

def is_render_eligible(flags: list[str]) -> bool:
    return not (set(flags) & FATAL_FLAGS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_probe.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_pipeline/probe.py tests/test_probe.py
git commit -m "feat: probe flag-judgment logic (thresholds from config, fatal-flag gating)"
```

---

## Task 5: Probe — OCC topology reader (no mesh)

**Files:**
- Modify: `src/cad_pipeline/probe.py` (add `probe_one`)
- Test: `tests/test_probe.py` (add an integration test gated on OCP)

`probe_one` reads a STEP via OCC and traverses topology — it NEVER calls `BRepMesh`.
On any failure it returns a structured result with `probe_status` set, never raises.

- [ ] **Step 1: Write the failing test (OCP-gated + a cube fixture)**

```python
# add to tests/test_probe.py
import pytest

ocp = pytest.importorskip("OCP")  # skip on machines without OpenCASCADE

def _write_cube_step(path):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    box = BRepPrimAPI_MakeBox(10.0, 20.0, 5.0).Shape()
    w = STEPControl_Writer()
    w.Transfer(box, STEPControl_AsIs)
    w.Write(str(path))

def test_probe_one_cube(tmp_path):
    from cad_pipeline.probe import probe_one
    p = tmp_path / "cube.step"
    _write_cube_step(p)
    res = probe_one(str(p))
    assert res["probe_status"] == "done"
    assert res["probe_n_solids"] == 1
    assert res["probe_n_faces"] == 6          # a box has 6 faces
    assert res["probe_n_edges"] == 12
    dims = sorted(res["probe_bbox_dims"])
    assert dims[0] == pytest.approx(5.0, abs=0.1)
    assert dims[2] == pytest.approx(20.0, abs=0.1)

def test_probe_one_unreadable(tmp_path):
    from cad_pipeline.probe import probe_one
    p = tmp_path / "junk.step"
    p.write_bytes(b"not a real step file")
    res = probe_one(str(p))
    assert res["probe_status"] == "read_fail"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_probe.py -k probe_one -v`
Expected: FAIL with `AttributeError`/`ImportError: cannot import name 'probe_one'`

- [ ] **Step 3: Add `probe_one` to `probe.py`**

```python
# append to src/cad_pipeline/probe.py

def _count(shape, topabs_enum) -> int:
    from OCP.TopExp import TopExp_Explorer
    exp = TopExp_Explorer(shape, topabs_enum)
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n

def probe_one(src_path: str) -> dict:
    """Read STEP + traverse topology. NO meshing. Never raises."""
    res = {"probe_n_faces": None, "probe_n_solids": None, "probe_n_edges": None,
           "probe_bbox_dims": None, "probe_bbox_ratio": None,
           "probe_status": "pending", "probe_error": None}
    try:
        from OCP.STEPControl import STEPControl_Reader
        from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_EDGE
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        reader = STEPControl_Reader()
        if reader.ReadFile(src_path) != 1:
            res["probe_status"] = "read_fail"
            return res
        reader.TransferRoots()
        shape = reader.OneShape()

        res["probe_n_faces"] = _count(shape, TopAbs_FACE)
        res["probe_n_solids"] = _count(shape, TopAbs_SOLID)
        res["probe_n_edges"] = _count(shape, TopAbs_EDGE)

        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box)
        xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
        dims = [xmax - xmin, ymax - ymin, zmax - zmin]
        res["probe_bbox_dims"] = dims
        mn = min(dims)
        res["probe_bbox_ratio"] = (max(dims) / mn) if mn > 1e-9 else float("inf")
        res["probe_status"] = "done"
    except Exception as e:
        res["probe_status"] = "probe_error"
        res["probe_error"] = f"{type(e).__name__}: {e}"[:300]
    return res
```

Note: `BRepBndLib.Add_s` is the static method name in OCP; if the pod's binding
exposes it as `BRepBndLib.Add`, use that. The `bbox_ratio` is `inf` for degenerate
parts, which `judge_flags` treats as degenerate (`inf > max_bbox_ratio`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_probe.py -k probe_one -v`
Expected: PASS (cube: 6 faces, 12 edges, 1 solid)

- [ ] **Step 5: Commit**

```bash
git add src/cad_pipeline/probe.py tests/test_probe.py
git commit -m "feat: probe_one reads STEP topology without meshing (fault-isolated)"
```

---

## Task 6: Probe — parallel runner with single serial writer

**Files:**
- Modify: `src/cad_pipeline/probe.py` (add `run_probe`)
- Create: `scripts/run_probe.py`
- Test: `tests/test_probe.py` (add `run_probe` end-to-end test)

Many worker processes probe in parallel; ONE writer commits to Lance to avoid version
conflicts. Restartable: only rows with `probe_status == "pending"` are processed.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_probe.py
def test_run_probe_updates_only_pending(tmp_path, monkeypatch):
    from cad_pipeline import probe as probe_mod
    from cad_pipeline.manifest import open_or_create, new_row
    from cad_pipeline.config import Config

    tbl = open_or_create(tmp_path / "manifest.lance")
    tbl.add([
        new_row("abc/1", "abc", "/x/1.step", 2.0),
        new_row("abc/2", "abc", "/x/2.step", 80.0),
    ])

    # stub OCC read: id 1 = clean cube, id 2 = complex
    fake = {
        "/x/1.step": {"probe_n_faces": 6, "probe_n_solids": 1, "probe_n_edges": 12,
                      "probe_bbox_dims": [10, 20, 5], "probe_bbox_ratio": 4.0,
                      "probe_status": "done", "probe_error": None},
        "/x/2.step": {"probe_n_faces": 9000, "probe_n_solids": 1, "probe_n_edges": 4,
                      "probe_bbox_dims": [10, 20, 5], "probe_bbox_ratio": 4.0,
                      "probe_status": "done", "probe_error": None},
    }
    monkeypatch.setattr(probe_mod, "probe_one", lambda p: fake[p])

    n = probe_mod.run_probe(Config(data_root=tmp_path), tbl, workers=1)
    assert n == 2
    rows = {r["model_id"]: r for r in tbl.to_arrow().to_pylist()}
    assert rows["abc/1"]["render_eligible"] is True
    assert rows["abc/1"]["quality_flags"] == []
    assert rows["abc/2"]["render_eligible"] is False
    assert "too_complex" in rows["abc/2"]["quality_flags"]
    assert "oversized" in rows["abc/2"]["quality_flags"]   # 80MB
    # rerun probes nothing (all done now)
    assert probe_mod.run_probe(Config(data_root=tmp_path), tbl, workers=1) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_probe.py -k run_probe -v`
Expected: FAIL with `AttributeError: run_probe`

- [ ] **Step 3: Add `run_probe` to `probe.py`**

```python
# append to src/cad_pipeline/probe.py
from concurrent.futures import ProcessPoolExecutor, as_completed
from cad_pipeline.config import Config

def _probe_task(args):
    model_id, src_path, file_size_mb = args
    metrics = probe_one(src_path)
    return model_id, file_size_mb, metrics

def run_probe(cfg: Config, tbl, workers: int = 24, batch: int = 2000) -> int:
    """Probe all pending rows. Parallel workers, single serial Lance writer.
    Returns number of rows updated."""
    df = tbl.to_arrow().to_pylist()
    pending = [(r["model_id"], r["src_path"], r["file_size_mb"])
               for r in df if r["probe_status"] == "pending"]
    if not pending:
        return 0

    updated = 0
    pending_updates = []

    def flush():
        nonlocal pending_updates, updated
        for u in pending_updates:
            tbl.update(where=f"model_id = '{u['model_id']}'", values=u["values"])
        updated += len(pending_updates)
        pending_updates = []

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_probe_task, p) for p in pending]
        for fut in as_completed(futures):
            model_id, file_size_mb, m = fut.result()
            flags = []
            if m["probe_status"] == "read_fail":
                flags = ["step_read_fail"]
            elif m["probe_status"] == "done":
                flags = judge_flags(cfg, file_size_mb, m["probe_n_faces"],
                                    m["probe_n_solids"], m["probe_bbox_dims"])
            values = {**{k: m[k] for k in (
                "probe_n_faces", "probe_n_solids", "probe_n_edges",
                "probe_bbox_dims", "probe_bbox_ratio", "probe_status", "probe_error")},
                "quality_flags": flags,
                "render_eligible": is_render_eligible(flags)}
            pending_updates.append({"model_id": model_id, "values": values})
            if len(pending_updates) >= batch:
                flush()
    flush()
    return updated
```

```python
# scripts/run_probe.py
import argparse
from pathlib import Path
from cad_pipeline.config import Config
from cad_pipeline.manifest import open_or_create
from cad_pipeline.probe import run_probe

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()
    cfg = Config(data_root=args.data_root)
    tbl = open_or_create(cfg.manifest_path)
    n = run_probe(cfg, tbl, workers=args.workers)
    print(f"Probed {n} rows")
```

Note: `tbl.update(where=...)` per row is simple and correct for the single-writer model.
If the real 1M-row run shows update throughput is the bottleneck, switch to the
delete-pending + add-batch pattern — but probe's bottleneck is OCC parsing, not the
writer, so per-row update is the right starting point (YAGNI).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_probe.py -k run_probe -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_pipeline/probe.py scripts/run_probe.py tests/test_probe.py
git commit -m "feat: parallel probe runner with single serial writer + restart on pending"
```

---

## Task 7: Download — port the proven downloader

**Files:**
- Create: `src/cad_pipeline/download.py`
- Create: `scripts/run_download.py`
- Test: `tests/test_download.py`

This is a near-verbatim port of `context/history/src/cad_retriever/data/download.py`,
which already encodes hard-won fixes: 7z-header size check, 5x retries, resume-by-redownload
(the ABC server has no range support), py7zr extraction with per-chunk markers. Keep that
logic; only change the proxy/paths to come from `Config`. Do NOT redesign it.

- [ ] **Step 1: Write the failing test (header check is the unit-testable core)**

```python
# tests/test_download.py
from cad_pipeline.download import get_expected_size, is_complete

SEVENZ_MAGIC = bytes.fromhex("377abcaf271c")

def test_get_expected_size_rejects_non_7z(tmp_path):
    p = tmp_path / "bad.7z"
    p.write_bytes(b"\x00" * 40)
    assert get_expected_size(p) == -1

def test_get_expected_size_parses_header(tmp_path):
    import struct
    p = tmp_path / "ok.7z"
    # magic(6) + 6 bytes pad to offset 12, then int64 offset, int64 size
    header = SEVENZ_MAGIC + b"\x00" * 6 + struct.pack("<q", 100) + struct.pack("<q", 200)
    p.write_bytes(header + b"\x00" * 400)
    # expected = offset + size + 32 = 100 + 200 + 32
    assert get_expected_size(p) == 332

def test_is_complete_false_for_small_file(tmp_path):
    p = tmp_path / "tiny.7z"
    p.write_bytes(b"\x00" * 10)
    assert is_complete(p) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_download.py -v`
Expected: FAIL with `ModuleNotFoundError: cad_pipeline.download`

- [ ] **Step 3: Write `download.py`** (port; public names `get_expected_size`, `is_complete`)

```python
# src/cad_pipeline/download.py
import subprocess, struct, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import py7zr
from tqdm import tqdm

ABC_STEP_LIST_URL = "https://deep-geometry.github.io/abc-dataset/data/step_v00.txt"
_print_lock = threading.Lock()

def get_expected_size(path: Path) -> int:
    try:
        with open(path, "rb") as f:
            data = f.read(28)
        if len(data) < 28 or data[:6] != bytes.fromhex("377abcaf271c"):
            return -1
        offset = struct.unpack("<q", data[12:20])[0]
        size = struct.unpack("<q", data[20:28])[0]
        return offset + size + 32
    except Exception:
        return -1

def is_complete(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1_000_000:
        return False
    expected = get_expected_size(path)
    return expected > 0 and path.stat().st_size >= expected

def _download_chunk(url, filename, chunks_dir, proxy, max_retries=5):
    cp = chunks_dir / filename
    if is_complete(cp):
        return filename, True
    for attempt in range(max_retries):
        if cp.exists():
            cp.unlink()  # server has no resume; redownload
        try:
            subprocess.run(["curl", "-x", proxy, "-L", "--retry", "3",
                            "--retry-delay", "5", "--max-time", "3600",
                            "-o", str(cp), url],
                           check=True, capture_output=True, timeout=3600)
            if is_complete(cp):
                return filename, True
        except Exception as e:
            with _print_lock:
                print(f"  {filename}: attempt {attempt+1} failed: {e}", flush=True)
    return filename, False

def download_abc(cfg, parallel: int = 8, verify: bool = True):
    cfg.abc_dir.mkdir(parents=True, exist_ok=True)
    list_path = cfg.abc_dir / "step_v00.txt"
    if not list_path.exists():
        subprocess.run(["curl", "-x", cfg.proxy, "-o", str(list_path),
                        ABC_STEP_LIST_URL], check=True)
    lines = list_path.read_text().strip().split("\n")
    chunks = [(l.split()[0], l.split()[1]) for l in lines if l.strip()]
    cfg.chunks_dir.mkdir(parents=True, exist_ok=True)
    print(f"ABC: {len(chunks)} chunks (parallel={parallel})")

    failed = []
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futs = {ex.submit(_download_chunk, u, f, cfg.chunks_dir, cfg.proxy): f
                for u, f in chunks}
        for fut in tqdm(as_completed(futs), total=len(chunks), desc="Download"):
            f, ok = fut.result()
            if not ok:
                failed.append(f)
    if failed:
        print(f"WARNING: {len(failed)} chunks failed: {failed}")

    cfg.step_dir.mkdir(parents=True, exist_ok=True)
    for cf in tqdm(sorted(cfg.chunks_dir.glob("*.7z")), desc="Extract"):
        marker = cfg.step_dir / f".extracted_{cf.stem}"
        if marker.exists() or not is_complete(cf):
            continue
        try:
            with py7zr.SevenZipFile(cf, mode="r") as z:
                z.extractall(path=str(cfg.step_dir))
            marker.touch()
        except Exception as e:
            print(f"WARNING: extract failed {cf.name}: {e}")

    n = sum(1 for _ in cfg.step_dir.rglob("*.step"))
    print(f"Extracted {n} STEP files")
    if verify and n < 900_000:
        raise RuntimeError(f"Expected ~1M STEP, got {n}; download incomplete")
    return n
```

```python
# scripts/run_download.py
import argparse
from pathlib import Path
from cad_pipeline.config import Config
from cad_pipeline.download import download_abc

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    cfg = Config(data_root=args.data_root)
    download_abc(cfg, parallel=args.parallel, verify=not args.no_verify)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_download.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_pipeline/download.py scripts/run_download.py tests/test_download.py
git commit -m "feat: port ABC downloader (7z header check, retries, resume, extract)"
```

---

## Task 8: Report — histogram + flag summary (DuckDB over the manifest)

**Files:**
- Create: `src/cad_pipeline/report.py`
- Create: `scripts/run_report.py`
- Test: `tests/test_report.py`

This produces deliverables #2 and #3 from the spec: the geometry-complexity histogram
(used to refine thresholds) and the flag-count / render_eligible summary (how far from
the 500K target). DuckDB reads the Lance table via its Arrow export.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from cad_pipeline.manifest import open_or_create, new_row
from cad_pipeline.report import summarize

def _done(model_id, faces, solids, size_mb, flags):
    r = new_row(model_id, "abc", f"/x/{model_id}.step", size_mb)
    r.update(probe_n_faces=faces, probe_n_solids=solids, probe_status="done",
             probe_bbox_dims=[1, 1, 1], probe_bbox_ratio=1.0,
             quality_flags=flags, render_eligible=(len(flags) == 0))
    return r

def test_summarize_counts(tmp_path):
    tbl = open_or_create(tmp_path / "manifest.lance")
    tbl.add([
        _done("abc/1", 100, 1, 2.0, []),
        _done("abc/2", 9000, 1, 2.0, ["too_complex"]),
        _done("abc/3", 1, 1, 80.0, ["too_simple", "oversized"]),
    ])
    s = summarize(tbl)
    assert s["total"] == 3
    assert s["render_eligible"] == 1
    assert s["flag_counts"]["too_complex"] == 1
    assert s["flag_counts"]["too_simple"] == 1
    assert s["flag_counts"]["oversized"] == 1
    # histogram buckets present for n_faces
    assert "n_faces_hist" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: cad_pipeline.report`

- [ ] **Step 3: Write `report.py`**

```python
# src/cad_pipeline/report.py
from collections import Counter

def summarize(tbl) -> dict:
    rows = tbl.to_arrow().to_pylist()
    done = [r for r in rows if r["probe_status"] == "done"]
    flag_counts = Counter()
    for r in rows:
        for f in (r["quality_flags"] or []):
            flag_counts[f] += 1
    # coarse log-ish histogram for n_faces
    buckets = [0, 3, 10, 50, 200, 1000, 5000, 20000, float("inf")]
    hist = {f"{buckets[i]}-{buckets[i+1]}": 0 for i in range(len(buckets) - 1)}
    for r in done:
        nf = r["probe_n_faces"] or 0
        for i in range(len(buckets) - 1):
            if buckets[i] <= nf < buckets[i + 1]:
                hist[f"{buckets[i]}-{buckets[i+1]}"] += 1
                break
    return {
        "total": len(rows),
        "probed": len(done),
        "render_eligible": sum(1 for r in rows if r["render_eligible"] is True),
        "flag_counts": dict(flag_counts),
        "n_faces_hist": hist,
    }

def format_report(s: dict) -> str:
    lines = [f"total={s['total']}  probed={s['probed']}  "
             f"render_eligible={s['render_eligible']}", "", "flag counts:"]
    for k, v in sorted(s["flag_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"  {k:16s} {v}")
    lines += ["", "n_faces histogram:"]
    for k, v in s["n_faces_hist"].items():
        lines.append(f"  {k:14s} {v}")
    return "\n".join(lines)
```

```python
# scripts/run_report.py
import argparse, json
from pathlib import Path
from cad_pipeline.config import Config
from cad_pipeline.manifest import open_or_create
from cad_pipeline.report import summarize, format_report

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    cfg = Config(data_root=args.data_root)
    s = summarize(open_or_create(cfg.manifest_path))
    print(json.dumps(s, indent=2) if args.json else format_report(s))
```

Note: the histogram uses pure-Python bucketing (no DuckDB dependency at runtime) so it
works anywhere the manifest opens. DuckDB stays available for ad-hoc threshold queries
against the same Lance table when refining the cutoffs.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cad_pipeline/report.py scripts/run_report.py tests/test_report.py
git commit -m "feat: probe report — n_faces histogram + flag counts + render_eligible total"
```

---

## Task 9: End-to-end smoke + full-suite run

**Files:**
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write a no-OCC end-to-end test (ingest -> stubbed probe -> report)**

```python
# tests/test_smoke.py
from cad_pipeline import probe as probe_mod
from cad_pipeline.config import Config
from cad_pipeline.manifest import open_or_create
from cad_pipeline.ingest import ingest_abc
from cad_pipeline.report import summarize

def test_ingest_probe_report_flow(tmp_path, monkeypatch):
    step_dir = tmp_path / "abc_step" / "step"
    step_dir.mkdir(parents=True)
    (step_dir / "00000001.step").write_bytes(b"x" * 4096)
    (step_dir / "00000002.step").write_bytes(b"y" * 4096)
    tbl = open_or_create(tmp_path / "manifest.lance")
    assert ingest_abc(step_dir, tbl) == 2

    fake = {"probe_n_faces": 100, "probe_n_solids": 1, "probe_n_edges": 12,
            "probe_bbox_dims": [1, 1, 1], "probe_bbox_ratio": 1.0,
            "probe_status": "done", "probe_error": None}
    monkeypatch.setattr(probe_mod, "probe_one", lambda p: dict(fake))
    probe_mod.run_probe(Config(data_root=tmp_path), tbl, workers=1)

    s = summarize(tbl)
    assert s["total"] == 2 and s["render_eligible"] == 2
```

- [ ] **Step 2: Run the full suite**

Run: `python3 -m pytest -v`
Expected: ALL PASS (OCP-gated tests skip on machines without OpenCASCADE).

- [ ] **Step 3: Commit**

```bash
git add tests/test_smoke.py
git commit -m "test: end-to-end ingest->probe->report smoke (no OCC)"
```

---

## Operator runbook (on the pod)

After the plan is implemented, the experimenter runs in order:

```bash
cd /home/cc/cad-pipeline   # or wherever the package lives
PY=/root/miniconda3/bin/python3

# 1. download + extract 1M STEP (resumable; rerun safely)
$PY scripts/run_download.py --data-root /home/cc/data

# 2. register every extracted STEP into the manifest (idempotent)
$PY scripts/run_ingest.py --data-root /home/cc/data

# 3. probe topology, no mesh (restartable: only pending rows)
$PY scripts/run_probe.py --data-root /home/cc/data --workers 24

# 4. histogram + flag summary -> refine thresholds in config.py, rerun probe
$PY scripts/run_report.py --data-root /home/cc/data
```

The report's histogram is the input for setting final thresholds (spec section 5):
inspect the real `n_faces` / `file_size` distribution, edit `Config`, and rerun probe —
it only re-touches rows still `pending` (to re-probe all, the experimenter can reset
`probe_status` to pending, since re-judging is cheap and reading is the cost).

---

## Self-Review

- **Spec §2 download** → Task 7. **§2 ingest** → Task 3. **§2 probe** → Tasks 4-6.
- **Spec §3 multi-source** → `model_id = abc/<id>` (Task 3 `abc_model_id`) + `ingest_abc` adapter boundary.
- **Spec §4 schema (all columns + vector placeholder)** → Task 2 `MANIFEST_SCHEMA`.
- **Spec §5 probe judgment + thresholds-as-config** → Task 1 `Config`, Task 4 `judge_flags`/`FATAL_FLAGS`.
- **Spec §6 fault isolation** → Task 5 `probe_one` never raises; **single writer** → Task 6 `run_probe`; **restart on pending** → Task 6.
- **Spec §6 tests (cube/empty/oversized)** → Task 5 cube + read_fail; Task 4 flag matrix.
- **Spec §7 deliverables (manifest, histogram, flag summary)** → Tasks 2/3/6 (table), Task 8 (histogram + counts).

Type consistency: `probe_one` returns the exact keys `run_probe` reads; `judge_flags`
signature matches its callers in Task 6; `new_row` keys match `MANIFEST_SCHEMA` names.
