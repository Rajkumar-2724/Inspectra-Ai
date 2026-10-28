import io
from pathlib import Path
from PIL import Image
import pytest

from app.database.session import SessionLocal
from app.models.models import Product
from tests.test_metal_nut_real_ai import metal_nut_product


def test_metal_nut_defect_circles_and_ellipses(client, admin, metal_nut_product):
    nut_id = metal_nut_product

    scratch_path = Path("C:/Users/rkraj/metal_nut_dataset/metal_nut/test/scratch/000.png")
    if not scratch_path.exists():
        pytest.skip("Scratch test image not found")

    with open(scratch_path, "rb") as f:
        img_bytes = f.read()

    resp = client.post(
        "/api/inspect",
        headers=admin,
        data={
            "product_id": nut_id,
            "mode": "real",
            "product_code": "NUT-DEFECT-001",
        },
        files={"file": ("scratch_nut.png", img_bytes, "image/png")}
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["decision"] in ("REVIEW", "FAIL")
    assert data["image_width"] > 0
    assert data["image_height"] > 0

    # Verify defects array with circle/ellipse attributes
    defects = data.get("defects", [])
    assert len(defects) > 0, "Expected detected defect regions on scratch image"

    for d in defects:
        assert d["shape"] in ("ellipse", "circle")
        assert "center_x" in d and "center_y" in d
        assert "radius_x" in d and "radius_y" in d
        assert "angle" in d
        assert d["label"] == "unclassified_anomaly", "Must NOT fabricate defect class without trained classifier"
        assert d["confidence"] is None

    # Verify explanation regions
    expl = data.get("explanation", {})
    regions = expl.get("regions", [])
    assert len(regions) == len(defects)

    for r in regions:
        assert "original_geometry" in r
        geom = r["original_geometry"]
        assert geom["shape"] in ("ellipse", "circle")
        assert len(geom["center"]) == 2
        assert len(geom["axes"]) == 2
        assert "crop_data" in r, "Base64 zoomed crop thumbnail must be present"
        assert r["crop_data"].startswith("data:image/jpeg;base64,")

    # Verify PDF report generation
    pdf_resp = client.get(f"/api/inspections/{data['id']}/report", headers=admin)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 5000


def test_normal_image_does_not_force_circles(client, admin, metal_nut_product):
    nut_id = metal_nut_product

    good_path = Path("C:/Users/rkraj/metal_nut_dataset/metal_nut/test/good/000.png")
    if not good_path.exists():
        pytest.skip("Good test image not found")

    with open(good_path, "rb") as f:
        img_bytes = f.read()

    resp = client.post(
        "/api/inspect",
        headers=admin,
        data={
            "product_id": nut_id,
            "mode": "real",
            "product_code": "NUT-NORMAL-001",
        },
        files={"file": ("good_nut.png", img_bytes, "image/png")}
    )
    assert resp.status_code == 201
    data = resp.json()

    # Normal image test
    expl = data.get("explanation", {})
    # Should not produce fabricated defect circles
    assert expl.get("localization_status") in ("uncalibrated", "provisional", "calibrated")
    # Defect labels should never be fabricated
    for d in data.get("defects", []):
        assert d["label"] == "unclassified_anomaly"
