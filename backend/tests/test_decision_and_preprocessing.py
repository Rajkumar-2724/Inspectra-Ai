import io

import numpy as np
import pytest
from PIL import Image

from app.ai.decision_engine import DecisionEngine, ThresholdError
from app.ai.localization import DefectLocalizer, HeatmapProcessor
from app.ai.preprocessing import ImagePreprocessor, ImageValidationError, validate_image_bytes
from app.models import Decision


@pytest.mark.parametrize("score,exp", [(0.0, Decision.PASS), (0.3999, Decision.PASS), (0.4, Decision.REVIEW), (0.6999, Decision.REVIEW),
                                       (0.7, Decision.FAIL), (1.0, Decision.FAIL)])
def test_boundaries(score, exp):
    assert DecisionEngine.decide(score, 0.4, 0.7) == exp


@pytest.mark.parametrize("r,f", [(0.7, 0.4), (0.5, 0.5), (-0.1, 0.5), (0.2, 1.2)])
def test_invalid_thresholds(r, f):
    with pytest.raises(ThresholdError):
        DecisionEngine.validate_thresholds(r, f)


def test_invalid_score():
    for s in (-0.01, 1.01, float("nan")):
        with pytest.raises(ThresholdError):
            DecisionEngine.decide(s, 0.4, 0.7)


def _png(size=(100, 60), fmt="PNG"):
    b = io.BytesIO()
    Image.new("RGB", size, (120, 130, 140)).save(b, fmt)
    return b.getvalue()


def test_validation():
    img, ext = validate_image_bytes(_png(), 10_000_000)
    assert ext == "png"
    for bad in (b"", b"not an image at all", _png(fmt="GIF") if False else b"GIF89a" + b"0" * 30):
        with pytest.raises(ImageValidationError):
            validate_image_bytes(bad, 10_000_000)
    with pytest.raises(ImageValidationError):
        validate_image_bytes(_png(), 10)  # too large
    with pytest.raises(ImageValidationError):
        validate_image_bytes(_png((8, 8)), 10_000_000)  # too small
    b = io.BytesIO()
    Image.new("RGB", (80, 80)).save(b, "BMP")
    with pytest.raises(ImageValidationError):
        validate_image_bytes(b.getvalue(), 10_000_000)  # unsupported type


def test_exif_orientation_and_resize():
    im = Image.new("RGB", (1200, 600), (10, 20, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 270 -> portrait
    b = io.BytesIO()
    im.save(b, "JPEG", exif=exif)
    img, _ = validate_image_bytes(b.getvalue(), 10_000_000)
    p = ImagePreprocessor(max_side=300).process(img)
    h, w = p.rgb.shape[:2]
    assert h > w and max(h, w) == 300  # orientation fixed, aspect ratio preserved
    assert p.original_size == (600, 1200)


def test_localizer_finds_regions():
    hm = np.zeros((100, 100), np.float32)
    hm[20:40, 30:60] = 0.9
    hm[80:82, 5:7] = 0.9  # too small -> ignored
    regs = DefectLocalizer().locate(hm, 0.5)
    assert len(regs) == 1 and (regs[0].x, regs[0].y, regs[0].w, regs[0].h) == (30, 20, 30, 20)
    assert DefectLocalizer().locate(hm * 0.1, 0.5) == []
    assert HeatmapProcessor().colorize(hm).shape == (100, 100, 3)
