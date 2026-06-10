import cv2
import numpy as np
from PIL import Image


def detect_edges(image: Image.Image) -> Image.Image:
    """Detect edges using Canny with auto-threshold.
    Returns binary edge map: white edges on black background.
    """
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)

    median = np.median(blurred)
    low = int(max(0, 0.33 * median))
    high = int(min(255, 0.66 * median))
    if high - low < 30:
        low = max(0, int(median) - 30)
        high = min(255, int(median) + 30)

    edges = cv2.Canny(blurred, low, high)
    return Image.fromarray(edges, mode="L")
