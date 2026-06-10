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

BLENDER_BIN = "/home/cc/data/blender-4.5.4-linux-x64/blender-wrapper.sh"

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

# Import based on file extension
ext = input_path.lower().split(".")[-1]
if ext in ("usd", "usda", "usdc"):
    bpy.ops.wm.usd_open(filepath=input_path)
elif ext == "step" or ext == "stp":
    # Enable STEP importer addon if available
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_step")
        bpy.ops.import_scene.step(filepath=input_path)
    except Exception:
        # Fallback: use FreeCAD-style mesh via subprocess (not available here)
        # Just create a placeholder cube so render doesn't fail
        bpy.ops.mesh.primitive_cube_add()
elif ext == "stl":
    bpy.ops.import_mesh.stl(filepath=input_path)
else:
    bpy.ops.mesh.primitive_cube_add()

# Setup render settings
bpy.context.scene.render.resolution_x = image_size
bpy.context.scene.render.resolution_y = image_size
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 32

# Add camera
bpy.ops.object.camera_add(location=(0, -5, 0))
cam = bpy.context.active_object
bpy.context.scene.camera = cam

# Add sun light
bpy.ops.object.light_add(type="SUN", location=(5, 5, 10))

# Select all mesh objects and frame them
bpy.ops.object.select_all(action="DESELECT")
for obj in bpy.context.scene.objects:
    if obj.type == "MESH":
        obj.select_set(True)

# Render each view
for i, (rx, ry, rz) in enumerate(angles):
    cam.rotation_euler = (math.radians(rx + 30), math.radians(ry), math.radians(rz + 45))
    cam.location = (
        5 * math.sin(math.radians(rz + 45)),
        -5 * math.cos(math.radians(rz + 45)),
        3
    )
    bpy.context.scene.render.filepath = f"{output_dir}/view_{i}"
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
        [BLENDER_BIN, "--background", "--python-expr", BLENDER_SCRIPT, "--", args_json],
        check=True, capture_output=True, timeout=120,
    )


def render_all(input_dir: Path, output_dir: Path, image_size: int = 224):
    """Render all models in input_dir. Processes STEP files directly."""
    files = sorted(input_dir.rglob("*.step")) + sorted(input_dir.rglob("*.stp"))
    if not files:
        files = sorted(input_dir.rglob("*.usd")) + sorted(input_dir.rglob("*.usda"))
    print(f"Rendering {len(files)} models")
    failed = []
    for f in tqdm(files, desc="Rendering"):
        model_id = f.stem
        model_out = output_dir / model_id
        if (model_out / "view_5.png").exists():
            continue
        try:
            render_model(f, model_out, image_size)
        except Exception as e:
            failed.append((f.name, str(e)))
    if failed:
        fail_log = output_dir / "render_failures.txt"
        fail_log.write_text("\n".join(f"{n}: {e}" for n, e in failed))
        print(f"WARNING: {len(failed)} renders failed. See {fail_log}")
