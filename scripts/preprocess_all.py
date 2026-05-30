"""Generate edge maps and synthetic sketches for all rendered models.
Runs in a continuous loop, picking up newly rendered models every pass.
"""
import argparse
import random
import time
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from cad_retriever.data.edge_detect import detect_edges
from cad_retriever.data.sketch_synth import synthesize_sketch

parser = argparse.ArgumentParser()
parser.add_argument("--renders", type=Path, default=Path("/home/cc/data/renders"))
parser.add_argument("--edges-out", type=Path, default=Path("/home/cc/data/edges"))
parser.add_argument("--sketches-out", type=Path, default=Path("/home/cc/data/sketches"))
parser.add_argument("--loop", action="store_true", default=True,
                    help="Keep looping to pick up new renders")
args = parser.parse_args()

while True:
    model_dirs = sorted(args.renders.iterdir())
    pending = [d for d in model_dirs
               if d.is_dir() and not (args.edges_out / d.name / "view_5.png").exists()]
    print(f"Processing {len(pending)} new models (total rendered: {len(model_dirs)})")

    if pending:
        for model_dir in tqdm(pending, desc="Preprocessing"):
            mid = model_dir.name
            edge_dir = args.edges_out / mid
            sketch_dir = args.sketches_out / mid
            edge_dir.mkdir(parents=True, exist_ok=True)
            sketch_dir.mkdir(parents=True, exist_ok=True)
            for view_file in sorted(model_dir.glob("view_*.png")):
                try:
                    img = Image.open(view_file)
                    edge = detect_edges(img, method="canny")
                    edge.save(edge_dir / view_file.name)
                    difficulty = random.uniform(0.2, 0.8)
                    sketch = synthesize_sketch(edge, difficulty=difficulty)
                    sketch.save(sketch_dir / view_file.name)
                except Exception as e:
                    print(f"Error processing {view_file}: {e}")

    # Check if rendering is complete
    edges_done = sum(1 for _ in args.edges_out.rglob("view_5.png"))
    renders_done = sum(1 for _ in args.renders.rglob("view_5.png"))
    print(f"Edges: {edges_done} / Renders: {renders_done}")

    if renders_done > 0 and edges_done >= renders_done * 0.99:
        print("Preprocessing complete!")
        break

    if not pending:
        # No new models yet, wait for renderer
        time.sleep(30)
