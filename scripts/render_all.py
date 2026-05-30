"""
Fast silhouette rendering pipeline for 1M CAD models.
Uses OCP (STEP→mesh) + PIL (silhouette projection).
No GPU/EGL required. ~1s/model with warm workers.
"""
import argparse
import os
import math
import numpy as np
from pathlib import Path
from tqdm import tqdm
from multiprocessing import Pool
from PIL import Image, ImageDraw


VIEW_ANGLES = [(30,0),(30,60),(30,120),(30,180),(30,240),(30,300)]


def render_silhouette(verts, faces, elev_deg, azim_deg, size=224):
    elev = math.radians(elev_deg)
    azim = math.radians(azim_deg)
    cos_a, sin_a = math.cos(azim), math.sin(azim)
    cos_e, sin_e = math.cos(elev), math.sin(elev)
    Ry = np.array([[cos_a, 0, sin_a], [0, 1, 0], [-sin_a, 0, cos_a]])
    Rx = np.array([[1, 0, 0], [0, cos_e, -sin_e], [0, sin_e, cos_e]])
    Vr = ((Rx @ Ry) @ verts.T).T
    px = ((Vr[:, 0] + 1.5) / 3.0 * size * 0.8 + size * 0.1).astype(int)
    py = size - 1 - ((Vr[:, 2] + 1.5) / 3.0 * size * 0.8 + size * 0.1).astype(int)
    img = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(img)
    f_sample = faces[np.random.choice(len(faces), min(1000, len(faces)), replace=False)]
    for tri in f_sample:
        pts = [(int(px[v].clip(0, size-1)), int(py[v].clip(0, size-1))) for v in tri]
        draw.polygon(pts, fill=(200, 200, 200), outline=(0, 0, 0))
    return img


def render_model(args_tuple):
    step_path, output_dir, image_size = args_tuple
    output_dir = Path(output_dir)
    if (output_dir / "view_5.png").exists():
        return True
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        import signal

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Timeout processing {step_path}")

        # 5s timeout per model — skip complex assemblies to maintain throughput
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(5)

        try:
            from OCP.STEPControl import STEPControl_Reader
            from OCP.BRepMesh import BRepMesh_IncrementalMesh
            import trimesh, tempfile

            reader = STEPControl_Reader()
            if reader.ReadFile(str(step_path)) != 1:
                signal.alarm(0)
                return False
            reader.TransferRoots()
            shape = reader.OneShape()
            BRepMesh_IncrementalMesh(shape, 1.0).Perform()  # coarser mesh = faster
        finally:
            signal.alarm(0)

        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            stl_path = f.name
        from OCP.StlAPI import StlAPI_Writer
        StlAPI_Writer().Write(shape, stl_path)

        mesh = trimesh.load(stl_path)
        os.unlink(stl_path)

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return False

        center = mesh.centroid
        scale = max(mesh.extents) if max(mesh.extents) > 0 else 1.0
        verts = (mesh.vertices - center) / scale
        faces = mesh.faces

        for i, (elev, azim) in enumerate(VIEW_ANGLES):
            img = render_silhouette(verts, faces, elev, azim, image_size)
            img.save(output_dir / f"view_{i}.png")
        return True
    except Exception:
        return False


def render_all_fast(input_dir: Path, output_dir: Path,
                    image_size: int = 224, workers: int = 32):
    files = sorted(input_dir.rglob("*.step")) + sorted(input_dir.rglob("*.stp"))
    print(f"Found {len(files)} STEP files")
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        (str(f), str(output_dir / f.stem), image_size)
        for f in files
        if not (output_dir / f.stem / "view_5.png").exists()
    ]
    already_done = len(files) - len(tasks)
    print(f"  Already done: {already_done}, To render: {len(tasks)}")

    if not tasks:
        print("All done!")
        return

    failed = 0
    # Use maxtasksperchild to recycle workers and avoid memory leaks
    from multiprocessing import Pool
    with Pool(processes=workers, maxtasksperchild=50) as pool:
        with tqdm(total=len(tasks), desc="Rendering") as pbar:
            for result in pool.imap_unordered(render_model, tasks, chunksize=1):
                if not result:
                    failed += 1
                pbar.update(1)

    done = sum(1 for f in files if (output_dir / f.stem / "view_5.png").exists())
    print(f"Done: {done}/{len(files)}, Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("/home/cc/data/abc_step/step"))
    parser.add_argument("--output", type=Path, default=Path("/home/cc/data/renders"))
    parser.add_argument("--size", type=int, default=224)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    render_all_fast(args.input, args.output, args.size, args.workers)
