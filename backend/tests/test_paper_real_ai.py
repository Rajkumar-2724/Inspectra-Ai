"""Automated tests for Plain Paper PatchCore integration & Real AI inference.
Verifies model readiness, ONNX validation, real inference execution, and contract guarantees.
"""
from pathlib import Path
import pytest
from sqlalchemy import select

from app.ai.model_registry import registry
from app.models import Product, ProductDefectClass, ModelVersion


@pytest.fixture
def paper_product(client, admin):
    """Ensures Plain Paper exists in the test DB with defect classes and registered PatchCore model."""
    from app.database.session import SessionLocal
    from tests.conftest import _tmp

    db = SessionLocal()
    p = db.execute(select(Product).where(Product.name == "Plain Paper")).scalar_one_or_none()
    if not p:
        p = Product(name="Plain Paper", category="Paper manufacturing", review_threshold=0.40, fail_threshold=0.70)
        p.defect_classes = [
            ProductDefectClass(name="dot"),
            ProductDefectClass(name="contamination"),
            ProductDefectClass(name="surface_blemish"),
        ]
        db.add(p)
        db.commit()
        db.refresh(p)

    # Use the real trained model artifact from models/paper/ if it exists, or create test artifact in _tmp/models
    test_models = _tmp / "models"
    test_models.mkdir(parents=True, exist_ok=True)
    
    repo_models = Path.cwd().parent / "models"
    real_onnx = repo_models / "paper" / "paper_patchcore_v1.onnx"
    real_meta = repo_models / "paper" / "paper_patchcore_v1.meta.json"
    
    if real_onnx.is_file() and real_meta.is_file():
        import shutil
        shutil.copy(real_onnx, test_models / "paper_patchcore_v1.onnx")
        shutil.copy(real_meta, test_models / "paper_patchcore_v1.meta.json")
        onnx_file_name = "paper_patchcore_v1.onnx"
    else:
        from tests.conftest import make_onnx_model
        make_onnx_model(test_models / "paper_patchcore_v1.onnx", size=512)
        onnx_file_name = "paper_patchcore_v1.onnx"

    # Register in DB
    m = db.execute(select(ModelVersion).where(ModelVersion.name == "patchcore-paper", ModelVersion.version == "1.0")).scalar_one_or_none()
    if not m:
        m = ModelVersion(
            name="patchcore-paper",
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


def test_paper_product_and_defect_classes(client, inspector, paper_product):
    """Verifies that Plain Paper is listed in the product catalog with its defect classes."""
    r = client.get("/api/products", headers=inspector)
    assert r.status_code == 200
    prods = r.json()
    paper = next((p for p in prods if p["name"] == "Plain Paper"), None)
    assert paper is not None
    assert paper["category"] == "Paper manufacturing"
    assert paper["review_threshold"] == 0.40
    assert paper["fail_threshold"] == 0.70
    assert set(paper["defect_classes"]) == {"dot", "contamination", "surface_blemish"}
    assert paper["real_mode_ready"] is True


def test_paper_model_readiness(client, inspector, paper_product):
    """Verifies that the PatchCore model for Plain Paper is validated as READY."""
    r = client.get("/api/models/status", headers=inspector)
    assert r.status_code == 200
    st = r.json()
    assert st["real_mode_available"] is True
    paper_st = st["products"].get(str(paper_product))
    assert paper_st is not None
    assert paper_st["ready"] is True
    assert paper_st["version"].startswith("patchcore-paper")


def test_paper_real_mode_inference(client, admin, inspector, paper_product):
    """Executes Real AI inference with Plain Paper and verifies contract compliance."""
    clean_sample = Path(r"C:\Users\rkraj\paper_dataset\train\good\0bdedfdc-f724-48ad-8a24-9c176da13c30.jpg")
    dot_sample = Path(r"C:\Users\rkraj\paper_dataset\test\dot\0d7b1323-6f2c-4699-b7c4-bef207b2d712.jpg")

    if not clean_sample.is_file():
        pytest.skip("Paper dataset not found at expected path")

    # 1. Test clean paper image
    with open(clean_sample, "rb") as f:
        files = {"file": ("paper_clean.jpg", f.read(), "image/jpeg")}
    form = {
        "product_id": str(paper_product),
        "mode": "real",
        "product_code": "PAPER-REAL-001",
        "batch_code": "BATCH-PAPER-01",
        "line_id": "LINE-02"
    }
    r_clean = client.post("/api/inspect", headers=inspector, files=files, data=form)
    assert r_clean.status_code == 201, r_clean.text
    insp_clean = r_clean.json()

    assert insp_clean["mode"] == "real"
    assert insp_clean["simulated"] is False
    assert insp_clean["product_name"] == "Plain Paper"
    assert insp_clean["model_version"].startswith("patchcore-paper:1.0")
    expl_clean = insp_clean.get("explanation", {})
    assert 0.0 <= insp_clean["score"] <= 1.0
    assert expl_clean.get("raw_score") is not None
    assert expl_clean.get("raw_score") < 2.0, f"Clean raw score should be < 2.0, got {expl_clean.get('raw_score')}"

    # 2. Test dotted paper defect image
    with open(dot_sample, "rb") as f:
        files_dot = {"file": ("paper_dot.jpg", f.read(), "image/jpeg")}
    form_dot = {
        "product_id": str(paper_product),
        "mode": "real",
        "product_code": "PAPER-REAL-002",
        "batch_code": "BATCH-PAPER-01",
        "line_id": "LINE-02"
    }
    r_dot = client.post("/api/inspect", headers=inspector, files=files_dot, data=form_dot)
    assert r_dot.status_code == 201, r_dot.text
    insp_dot = r_dot.json()
    expl_dot = insp_dot.get("explanation", {})

    assert insp_dot["mode"] == "real"
    assert insp_dot["product_name"] == "Plain Paper"
    assert expl_dot.get("raw_score") is not None
    assert expl_dot.get("raw_score") > 2.0
    assert insp_dot["decision"] in ("FAIL", "REVIEW")

    # 3. Verify cryptographic audit chain remains valid
    r_audit = client.get("/api/audit/verify", headers=admin)
    assert r_audit.status_code == 200
    assert r_audit.json()["valid"] is True
