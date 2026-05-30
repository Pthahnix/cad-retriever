import cv2
import numpy as np
from PIL import Image


def detect_edges(image: Image.Image, method: str = "canny") -> Image.Image:
    """Detect edges from a rendered CAD image.
    Returns a grayscale PIL Image with white edges on black background.
    """
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    if method == "canny":
        edges = cv2.Canny(gray, threshold1=50, threshold2=150)
    else:
        raise ValueError(f"Unknown method: {method}. Use 'canny'.")

    return Image.fromarray(edges)
