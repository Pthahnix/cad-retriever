import numpy as np
from PIL import Image
from cad_retriever.data.edge_detect import detect_edges


def test_detect_edges_output_shape():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img, method="canny")
    assert edges.size == (224, 224)
    assert edges.mode == "L"


def test_detect_edges_binary_output():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img, method="canny")
    arr = np.array(edges)
    unique = np.unique(arr)
    # Canny produces binary edges
    assert len(unique) <= 2
