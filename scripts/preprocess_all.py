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
