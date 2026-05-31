"""
Pyrender + EGL GPU offscreen rendering for 1M CAD models.
Reads STEP → STL (via OCP), then renders 6 views with pyrender.
"""
import os
os.environ["PYOPENGL_PLATFORM"] = "egl"

import argparse
import math
import numpy as np
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

            elev_rad = math.radians(elev)
            azim_rad = math.radians(azim)
            dist = 2.5
            cx = dist * math.cos(elev_rad) * math.sin(azim_rad)
            cy = dist * math.cos(elev_rad) * math.cos(azim_rad)
            cz = dist * math.sin(elev_rad)
            camera_pos = np.array([cx, cy, cz])

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
    import tempfile
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

        # Use a unique temp file to avoid race conditions with 24 parallel workers
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False,
                                         dir=str(TMP_DIR)) as f:
            stl_path = f.name
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
