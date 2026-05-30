import numpy as np
from PIL import Image
from cad_retriever.data.sketch_synth import synthesize_sketch


def test_synthesize_sketch_output_shape():
    edge_img = Image.fromarray(
        np.random.choice([0, 255], (224, 224), p=[0.8, 0.2]).astype(np.uint8)
    )
    sketch = synthesize_sketch(edge_img, difficulty=0.5)
    assert sketch.size == (224, 224)
    assert sketch.mode == "L"


def test_synthesize_sketch_varies_with_difficulty():
    edge_img = Image.fromarray(
        np.random.choice([0, 255], (224, 224), p=[0.7, 0.3]).astype(np.uint8)
    )
    sketch_easy = synthesize_sketch(edge_img, difficulty=0.1)
    sketch_hard = synthesize_sketch(edge_img, difficulty=0.9)
    # Higher difficulty = more perturbation = more different from original
    arr_orig = np.array(edge_img).astype(float)
    diff_easy = np.abs(np.array(sketch_easy).astype(float) - arr_orig).mean()
    diff_hard = np.abs(np.array(sketch_hard).astype(float) - arr_orig).mean()
    assert diff_hard > diff_easy
