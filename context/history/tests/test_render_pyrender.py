import numpy as np
import pytest
from pathlib import Path
from PIL import Image


def test_render_single_model(tmp_path):
    """Test that render_one produces 6 valid PNG images."""
    import trimesh

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
        assert arr.mean() < 250


def test_render_handles_empty_mesh(tmp_path):
    """Test that render gracefully handles degenerate meshes."""
    # Write a minimal invalid STL (header only, no triangles)
    stl_path = tmp_path / "empty.stl"
    stl_path.write_bytes(b'\x00' * 80 + b'\x00\x00\x00\x00')  # 80-byte header + 0 triangles

    from scripts.render_all import render_one_model
    output_dir = tmp_path / "output"
    result = render_one_model(str(stl_path), str(output_dir), 224)
    assert result is False
