import cv2
import numpy as np
from PIL import Image


def synthesize_sketch(edge_image: Image.Image, difficulty: float = 0.5) -> Image.Image:
    """Generate a synthetic hand-drawn sketch from an edge image.
    difficulty: 0.0 (clean edges) to 1.0 (heavily perturbed).
    """
    arr = np.array(edge_image).astype(np.float32)

    # Line jitter: randomly shift edge pixels
    if difficulty > 0.1:
        jitter_px = int(difficulty * 3)
        kernel_size = max(1, jitter_px * 2 + 1)
        arr = cv2.GaussianBlur(arr, (kernel_size, kernel_size), sigmaX=difficulty * 2)
        _, arr = cv2.threshold(arr, 80, 255, cv2.THRESH_BINARY)

    # Random line breaks: remove random segments
    if difficulty > 0.3:
        mask = np.random.random(arr.shape) > (difficulty * 0.3)
        arr = arr * mask

    # Thickness variation: dilate with random kernel
    if difficulty > 0.2:
        k = max(1, int(difficulty * 2))
        kernel = np.ones((k, k), np.uint8)
        arr = cv2.dilate(arr.astype(np.uint8), kernel, iterations=1).astype(np.float32)

    # Partial occlusion: black out random rectangles
    if difficulty > 0.6:
        h, w = arr.shape
        num_rects = int(difficulty * 3)
        for _ in range(num_rects):
            rh, rw = np.random.randint(10, 40, size=2)
            ry, rx = np.random.randint(0, h - rh), np.random.randint(0, w - rw)
            arr[ry:ry+rh, rx:rx+rw] = 0

    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))
