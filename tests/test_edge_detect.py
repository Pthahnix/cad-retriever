import numpy as np
from PIL import Image
from cad_retriever.data.edge_detect import detect_edges


def test_detect_edges_output_shape():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img)
    assert edges.size == (224, 224)
    assert edges.mode == "L"


def test_detect_edges_binary_output():
    img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    edges = detect_edges(img)
    arr = np.array(edges)
    unique = np.unique(arr)
    assert len(unique) <= 2


def test_detect_edges_finds_box_edges():
    """A grey box on white background should produce clear edges."""
    arr = np.ones((224, 224, 3), dtype=np.uint8) * 255
    arr[50:170, 50:170] = 128  # grey box
    img = Image.fromarray(arr)
    edges = detect_edges(img)
    edge_arr = np.array(edges)
    # Should have some white pixels (edges detected)
    assert edge_arr.sum() > 0
    # Edges should be near the box boundary
    assert edge_arr[100, 100] == 0  # center of box = no edge
