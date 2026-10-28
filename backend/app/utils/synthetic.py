"""Programmatic synthetic sample images for DEMO mode (not real product photos)."""
import io

import cv2
import numpy as np
from PIL import Image

SIZE = (512, 384)  # w, h


def _base(rng: np.random.Generator) -> np.ndarray:
    w, h = SIZE
    grad = np.linspace(150, 190, w, dtype=np.float32)[None, :].repeat(h, 0)
    noise = cv2.GaussianBlur(rng.normal(0, 9, (h, w)).astype(np.float32), (0, 0), 0.8)
    streak = cv2.GaussianBlur(rng.normal(0, 6, (h, 1)).astype(np.float32).repeat(w, 1), (0, 0), 1.2)
    g = np.clip(grad + noise + streak, 0, 255).astype(np.uint8)
    img = cv2.merge([g, g, np.clip(g.astype(np.int16) + 8, 0, 255).astype(np.uint8)])
    cv2.rectangle(img, (14, 14), (w - 15, h - 15), (110, 118, 128), 3)
    for cx, cy in ((46, 46), (w - 47, 46), (46, h - 47), (w - 47, h - 47)):
        cv2.circle(img, (cx, cy), 14, (60, 66, 76), -1)
        cv2.circle(img, (cx, cy), 14, (210, 214, 220), 2)
    cv2.circle(img, (w // 2, h // 2), 52, (96, 104, 116), 3)
    cv2.circle(img, (w // 2, h // 2), 18, (70, 76, 88), -1)
    for y in (110, 140, 244, 274):
        cv2.line(img, (90, y), (w - 90, y), (125, 132, 142), 2)
    return img


def make_sample(scenario: str, seed: int = 7) -> Image.Image:
    rng = np.random.default_rng(seed)
    img = _base(rng)
    w, h = SIZE
    if scenario == "obvious_defect":
        cv2.line(img, (120, 90), (400, 300), (35, 38, 44), 4)
        cv2.line(img, (125, 88), (405, 296), (215, 220, 226), 1)
        cv2.polylines(img, [np.array([[300, 120], [318, 150], [305, 175], [330, 205]])], False, (25, 25, 30), 3)
    elif scenario == "subtle_defect":
        ov = img.copy()
        cv2.ellipse(ov, (330, 200), (16, 9), 25, 0, 360, (128, 134, 146), -1)
        img = cv2.addWeighted(ov, 0.45, img, 0.55, 0)
    elif scenario == "unknown_defect":
        ov = img.copy()
        pts = np.array([[200, 280], [235, 262], [262, 290], [244, 322], [208, 318]])
        cv2.fillPoly(ov, [pts], (70, 110, 150))
        cv2.circle(ov, (290, 300), 9, (160, 90, 60), -1)
        img = cv2.addWeighted(ov, 0.7, img, 0.3, 0)
    elif scenario == "lighting_variation":
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 14, 1.0)
        img = cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)
        shade = np.linspace(0.55, 1.05, w, dtype=np.float32)[None, :, None]
        img = np.clip(img.astype(np.float32) * shade, 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def sample_png_bytes(scenario: str, seed: int = 7) -> bytes:
    buf = io.BytesIO()
    make_sample(scenario, seed).save(buf, "PNG")
    return buf.getvalue()
