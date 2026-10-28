"""Automated tests for PCB Controller Board (VisA pcb1) PatchCore integration & Real AI inference.
Verifies model readiness, ONNX validation, real inference execution, and contract guarantees.
"""
from pathlib import Path
import pytest
from sqlalchemy import select

from app.ai.model_registry import registry
from app.models import Product, ProductDefectClass, ModelVersion


@pytest.fixture
def pcb_product(client, admin):
    """Ensures PCB Controller Board exists in the test DB with defect classes and registered PatchCore model."""
    from app.database.session import SessionLocal
    from tests.conftest import _tmp

    db = SessionLocal()
    p = db.execute(select(Product).where(Product.name == "PCB Controller Board")).scalar_one_or_none()
    if not p:
        p = Product(name="PCB Controller Board", category="Electronics", review_threshold=0.40, fail_threshold=0.70)
        p.defect_classes = [
            ProductDefectClass(name="scratch"),
            ProductDefectClass(name="missing_component"),
            ProductDefectClass(name="burnt"),
            ProductDefectClass(name="solder_bridge"),
        ]
        db.add(p)
        db.commit()
        db.refresh(p)

    test_models = _tmp / "models"
    test_models.mkdir(parents=True, exist_ok=True)
    
    repo_models = Path.cwd().parent / "models"
    real_onnx = repo_models / "pcb1" / "patchcore_pcb1_v1.onnx"
    real_meta = repo_models / "pcb1" / "patchcore_pcb1_v1.meta.json"
    
    if real_onnx.is_file() and real_meta.is_file():
        import shutil
        pcb_dir = test_models / "pcb1"
        pcb_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(real_onnx, pcb_dir / "patchcore_pcb1_v1.onnx")
        shutil.copy(real_meta, pcb_dir / "patchcore_pcb1_v1.meta.json")
        onnx_file_name = "pcb1/patchcore_pcb1_v1.onnx"
    else:
        from tests.conftest import make_onnx_model
        make_onnx_model(test_models / "pcb1_patchcore.onnx", size=512)
        onnx_file_name = "pcb1_patchcore.onnx"

    # Register in DB
    m = db.execute(select(ModelVersion).where(ModelVersion.name == "patchcore-pcb1", ModelVersion.version == "1.0")).scalar_one_or_none()
    if not m:
        m = ModelVersion(
            name="patchcore-pcb1",
            version="1.0",
            model_type="patchcore",
            format="onnx",
            file_path=onnx_file_name,
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


def test_pcb_product_and_defect_classes(client, inspector, pcb_product):
    """Verifies that PCB Controller Board is listed in the product catalog with its defect classes."""
    r = client.get("/api/products", headers=inspector)
    assert r.status_code == 200
    prods = r.json()
    pcb = next((p for p in prods if p["name"] == "PCB Controller Board"), None)
    assert pcb is not None
    assert pcb["category"] == "Electronics"
    assert pcb["review_threshold"] == 0.40
    assert pcb["fail_threshold"] == 0.70
    assert pcb["real_mode_ready"] is True


def test_pcb_model_readiness(client, inspector, pcb_product):
    """Verifies that the PatchCore model for PCB Controller Board is validated as READY."""
    r = client.get("/api/models/status", headers=inspector)
    assert r.status_code == 200
    st = r.json()
    assert st["real_mode_available"] is True
    pcb_st = st["products"].get(str(pcb_product))
    assert pcb_st is not None
    assert pcb_st["ready"] is True
    assert pcb_st["version"].startswith("patchcore-pcb1")


def test_pcb_real_mode_inference(client, admin, inspector, pcb_product):
    """Executes Real AI inference with PCB Controller Board and verifies contract compliance."""
    repo_models = Path.cwd().parent / "models"
    clean_sample = repo_models / "pcb1" / "sample_images" / "pcb_normal.jpg"
    defective_sample = repo_models / "pcb1" / "sample_images" / "pcb_defective.jpg"

    if not clean_sample.is_file():
        pytest.skip("PCB sample images not generated yet")

    # 1. Test clean normal PCB image
    with open(clean_sample, "rb") as f:
        files = {"file": ("pcb_clean.jpg", f.read(), "image/jpeg")}
    form = {
        "product_id": str(pcb_product),
        "mode": "real",
        "product_code": "PCB-REAL-001",
        "batch_code": "BATCH-PCB-01",
        "line_id": "SMT-01"
    }
    r_clean = client.post("/api/inspect", headers=inspector, files=files, data=form)
    assert r_clean.status_code == 201, r_clean.text
    insp_clean = r_clean.json()

    assert insp_clean["mode"] == "real"
    assert insp_clean["simulated"] is False
    assert insp_clean["product_name"] == "PCB Controller Board"
    assert insp_clean["model_version"].startswith("patchcore-pcb1:1.0")
    expl_clean = insp_clean.get("explanation", {})
    assert 0.0 <= insp_clean["score"] <= 1.0
    assert insp_clean["decision"] == "PASS"

    # 2. Test defective PCB image
    with open(defective_sample, "rb") as f:
        files_def = {"file": ("pcb_defective.jpg", f.read(), "image/jpeg")}
    form_def = {
        "product_id": str(pcb_product),
        "mode": "real",
        "product_code": "PCB-REAL-002",
        "batch_code": "BATCH-PCB-01",
        "line_id": "SMT-01"
    }
    r_def = client.post("/api/inspect", headers=inspector, files=files_def, data=form_def)
    assert r_def.status_code == 201, r_def.text
    insp_def = r_def.json()
    expl_def = insp_def.get("explanation", {})

    assert insp_def["mode"] == "real"
    assert insp_def["product_name"] == "PCB Controller Board"
    assert insp_def["decision"] in ("FAIL", "REVIEW")
    assert insp_def["score"] >= 0.40
    # Must have detected defect regions
    assert len(insp_def.get("defects", [])) >= 1

    # 3. Verify cryptographic audit chain remains valid
    r_audit = client.get("/api/audit/verify", headers=admin)
    assert r_audit.status_code == 200
    assert r_audit.json()["valid"] is True
