import cv2
import numpy as np
from PIL import Image


def detect_edges(image: Image.Image, method: str = "canny") -> Image.Image:
    """Detect edges / produce sketch-like image from a rendered CAD image.
    Returns a grayscale PIL Image suitable for use as a sketch query.
    """
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    if method == "canny":
        # Renders are white (255) background with grey shapes.
        # Strategy: invert so shapes become dark on white (sketch-like),
        # then enhance contrast to make the shape more visible.
        inverted = 255 - gray  # shapes are now dark on white
        # Stretch contrast: map min→0, max→255
        mn, mx = inverted.min(), inverted.max()
        if mx > mn:
            stretched = ((inverted.astype(np.float32) - mn) / (mx - mn) * 255).astype(np.uint8)
        else:
            stretched = inverted
        # Apply CLAHE for local contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(stretched)
        return Image.fromarray(enhanced)
    else:
        raise ValueError(f"Unknown method: {method}. Use 'canny'.")
