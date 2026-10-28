"""Image validation, orientation normalisation and preprocessing."""
import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MIN_SIDE, MAX_SIDE_ACCEPTED = 32, 12000
Image.MAX_IMAGE_PIXELS = 100_000_000  # decompression-bomb guard


class ImageValidationError(ValueError):
    pass


def validate_image_bytes(data: bytes, max_bytes: int) -> tuple[Image.Image, str]:
    """Verify size, real image content (not just extension) and allowed format."""
    if not data:
        raise ImageValidationError("Empty file")
    if len(data) > max_bytes:
        raise ImageValidationError(f"File exceeds {max_bytes // (1024 * 1024)} MB limit")
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as e:
        raise ImageValidationError("File is not a valid image") from e
    if fmt not in ALLOWED_FORMATS:
        raise ImageValidationError("Unsupported image type; use JPG, PNG or WEBP")
    if min(img.size) < MIN_SIDE or max(img.size) > MAX_SIDE_ACCEPTED:
        raise ImageValidationError(f"Image dimensions {img.size} outside accepted range")
    return img, ALLOWED_FORMATS[fmt]


class OrientationNormalizer:
    """Applies EXIF orientation and converts to RGB. (Does not guess arbitrary rotations.)"""

    def normalize(self, img: Image.Image) -> Image.Image:
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")


@dataclass
class ProcessedImage:
    rgb: np.ndarray  # uint8 HxWx3, aspect-preserving resized
    original_size: tuple[int, int]  # (w, h)
    scale: float


class ImagePreprocessor:
    def __init__(self, max_side: int = 640, normalize_lighting: bool = False, denoise: bool = False):
        self.max_side, self.normalize_lighting, self.denoise = max_side, normalize_lighting, denoise
        self.orientation = OrientationNormalizer()

    def process(self, img: Image.Image) -> ProcessedImage:
        img = self.orientation.normalize(img)
        w, h = img.size
        scale = min(1.0, self.max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        arr = np.asarray(img, dtype=np.uint8).copy()
        if self.denoise:
            arr = cv2.fastNlMeansDenoisingColored(arr, None, 3, 3, 7, 21)
        if self.normalize_lighting:  # CLAHE on the L channel
            lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
            lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[..., 0])
            arr = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        return ProcessedImage(rgb=arr, original_size=(w, h), scale=scale)
