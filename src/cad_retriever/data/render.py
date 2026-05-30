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
