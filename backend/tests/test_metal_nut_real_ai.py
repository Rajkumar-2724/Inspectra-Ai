"""Automated tests for MVTec AD Metal Nut PatchCore integration & Real AI inference.
Verifies model readiness, ONNX validation, real inference execution, and contract guarantees.
"""
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai.model_registry import registry, validate_artifact
from app.models import Decision, ModelStatus, ModelVersion, Mode, Product, Role, User
from tests.conftest import png


@pytest.fixture
def metal_nut_product(client, admin):
    """Ensures Metal Nut exists in the test DB with defect classes and registered PatchCore model."""
    from app.database.session import SessionLocal
    from tests.conftest import _tmp, make_onnx_model

    db = SessionLocal()
    p = db.execute(select(Product).where(Product.name == "Metal Nut")).scalar_one_or_none()
    if not p:
        from app.models import ProductDefectClass
        p = Product(name="Metal Nut", category="Machined fastener", review_threshold=0.40, fail_threshold=0.70)
        p.defect_classes = [
            ProductDefectClass(name="bent"),
            ProductDefectClass(name="color"),
            ProductDefectClass(name="flip"),
            ProductDefectClass(name="scratch"),
        ]
        db.add(p)
        db.commit()
        db.refresh(p)

    # Place a valid ONNX artifact directly in test models directory (not subfolder, for conftest cleanup)
    test_models = _tmp / "models"
    test_models.mkdir(parents=True, exist_ok=True)
    onnx_file = test_models / "patchcore_metal_nut_v1.onnx"
    make_onnx_model(onnx_file, size=256)

    # Register in DB
    m = db.execute(select(ModelVersion).where(ModelVersion.name == "patchcore-metal-nut", ModelVersion.version == "1.0")).scalar_one_or_none()
    if not m:
        m = ModelVersion(
            name="patchcore-metal-nut",
            version="1.0",
            model_type="patchcore",
            format="onnx",
            file_path="patchcore_metal_nut_v1.onnx",
            product_id=p.id
        )
        db.add(m)
        db.flush()

    m.product_id = p.id
    registry.validate_and_store(db, m)
    p.patchcore_model_id = m.id
    db.commit()
    pid = p.id
    db.close()
    return pid


def test_metal_nut_product_and_defect_classes(client, inspector, metal_nut_product):
    """Verifies that Metal Nut is listed in the product catalog with its 4 defect classes."""
    r = client.get("/api/products", headers=inspector)
    assert r.status_code == 200
    prods = r.json()
    nut = next((p for p in prods if p["name"] == "Metal Nut"), None)
    assert nut is not None
    assert nut["category"] == "Machined fastener"
    assert nut["review_threshold"] == 0.40
    assert nut["fail_threshold"] == 0.70
    assert set(nut["defect_classes"]) == {"bent", "color", "flip", "scratch"}


def test_metal_nut_model_readiness(client, inspector, metal_nut_product):
    """Verifies that the PatchCore model for Metal Nut is validated as READY."""
    r = client.get("/api/models/status", headers=inspector)
    assert r.status_code == 200
    st = r.json()
    assert st["real_mode_available"] is True
    nut_st = st["products"].get(str(metal_nut_product))
    assert nut_st is not None
    assert nut_st["ready"] is True
    assert nut_st["version"].startswith("patchcore-metal-nut")


def test_metal_nut_real_mode_inference(client, admin, inspector, metal_nut_product):
    """Executes Real AI inference with Metal Nut and verifies contract compliance."""
    files = {"file": ("metal_nut_test.png", png("good"), "image/png")}
    form = {
        "product_id": str(metal_nut_product),
        "mode": "real",
        "product_code": "MN-REAL-001",
        "batch_code": "BATCH-MN-01",
        "line_id": "LINE-01"
    }
    r = client.post("/api/inspect", headers=inspector, files=files, data=form)
    assert r.status_code == 201, r.text
    insp = r.json()

    # Verify Real AI Contract
    assert insp["mode"] == "real"
    assert insp["simulated"] is False
    assert insp["model_version"].startswith("patchcore-metal-nut:1.0")
    assert 0.0 <= insp["score"] <= 1.0
    assert insp["latency_ms"] > 0
    assert insp["decision"] in ("PASS", "REVIEW", "FAIL")

    # Verify Anomaly Map and Image Channels Exist
    r_img = client.get(f"/api/inspections/{insp['id']}/images/heatmap", headers=inspector)
    assert r_img.status_code == 200
    assert "image/png" in r_img.headers.get("content-type", "")

    # Verify Cryptographic Audit Chain (requires admin role)
    r_audit = client.get("/api/audit/verify", headers=admin)
    assert r_audit.status_code == 200
    assert r_audit.json()["valid"] is True


def test_metal_nut_demo_mode_rejected(client, inspector, metal_nut_product):
    """Ensures Demo Mode is completely removed and requests for demo mode return 422 Unprocessable Entity."""
    files = {"file": ("metal_nut_demo.png", png("good"), "image/png")}
    form = {
        "product_id": str(metal_nut_product),
        "mode": "demo",
        "product_code": "MN-DEMO-001"
    }
    r = client.post("/api/inspect", headers=inspector, files=files, data=form)
    assert r.status_code == 422


def test_unready_product_real_mode_refusal(client, inspector):
    """Ensures that products without ready models explicitly return 409 without fallback."""
    from app.database.session import SessionLocal
    db = SessionLocal()
    # Find a product with no model assigned
    unready = db.execute(select(Product).where(Product.patchcore_model_id.is_(None))).scalars().first()
    db.close()
    if unready:
        files = {"file": ("test.png", png("good"), "image/png")}
        form = {"product_id": str(unready.id), "mode": "real"}
        r = client.post("/api/inspect", headers=inspector, files=files, data=form)
        assert r.status_code == 409
        detail = r.json().get("detail", {})
        assert detail.get("code") == "REAL_MODE_UNAVAILABLE"
