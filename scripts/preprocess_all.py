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
