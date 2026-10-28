import numpy as np
import pytest
from PIL import Image

from app.ai.classifier_adapter import ClassifierAdapter
from app.ai.inspection_engine import InspectionEngine
from app.ai.model_registry import ModelNotReadyError, RealModels
from app.ai.patchcore_adapter import PatchCoreOutput
from app.ai.preprocessing import ImagePreprocessor
from app.database.session import SessionLocal
from app.models import Decision, Product
from tests.conftest import _tmp, do_inspect, make_onnx_model, png

REG = {"name": "pc", "version": "1.0", "model_type": "patchcore", "format": "onnx", "file_path": "pc.onnx"}


def test_register_missing_file(client, admin, inspector):
    r = client.post("/api/models/register", headers=admin, json=REG)
    assert r.status_code == 201 and r.json()["status"] == "FILE_MISSING"
    assert client.post("/api/models/register", headers=admin, json=REG).status_code == 409
    assert client.get("/api/models", headers=inspector).json()[0]["status"] == "FILE_MISSING"


def test_register_rejects_traversal_and_pickle(client, admin):
    assert client.post("/api/models/register", headers=admin, json={**REG, "file_path": "../../etc/passwd"}).status_code == 422
    assert client.post("/api/models/register", headers=admin, json={**REG, "file_path": "/etc/passwd"}).status_code == 422
    (_tmp / "models" / "evil.pth").write_bytes(b"pickle")
    r = client.post("/api/models/register", headers=admin, json={**REG, "name": "evil", "file_path": "evil.pth", "format": "torchscript"})
    assert r.json()["status"] == "INVALID" and "Pickle" in r.json()["status_detail"]


def test_invalid_artifacts(client, admin):
    (_tmp / "models" / "junk.onnx").write_bytes(b"not onnx")
    assert client.post("/api/models/register", headers=admin, json={**REG, "name": "jj", "file_path": "junk.onnx"}).json()["status"] == "INVALID"  # no metadata
    (_tmp / "models" / "junk.meta.json").write_text('{"input_size":[64,64],"score_min":0,"score_max":1}')
    r = client.post("/api/models/register", headers=admin, json={**REG, "name": "jj2", "version": "2", "file_path": "junk.onnx"})
    assert r.json()["status"] == "INVALID" and "ONNX" in r.json()["status_detail"]


def test_real_mode_with_valid_onnx_artifact(client, admin, inspector, product_id):
    """Exercises the real path with a TEST-ONLY untrained ONNX graph (no AI claims made)."""
    make_onnx_model(_tmp / "models" / "pc.onnx")
    r = client.post("/api/models/register", headers=admin, json={**REG, "product_id": product_id, "assign_to_product": True})
    assert r.json()["status"] == "READY", r.json()
    assert client.get("/api/models/status", headers=inspector).json()["real_mode_available"] is True
    i = do_inspect(client, inspector, product_id, "obvious_defect", mode="real")
    assert i.status_code == 201, i.text
    j = i.json()
    assert j["mode"] == "real" and j["simulated"] is False and j["model_version"].startswith("pc:1.0")
    assert 0 <= j["score"] <= 1 and j["latency_ms"] > 0
    assert "SIMULATED" not in j["explanation"]["disclaimer"]
    assert client.get(f"/api/inspections/{j['id']}/report", headers=inspector).content[:5] == b"%PDF-"
    assert client.get("/api/audit/verify", headers=admin).json()["valid"]
    # Replacing the file with garbage must make real mode refuse again (no stale cache, no demo fallback)
    (_tmp / "models" / "pc.onnx").write_bytes(b"corrupt!")
    assert do_inspect(client, inspector, product_id, "good", mode="real").status_code == 409


def test_model_must_match_product(client, admin, inspector, product_id):
    make_onnx_model(_tmp / "models" / "pc.onnx")
    other = client.post("/api/products", headers=admin, json={"name": "Other", "category": "Fabric"}).json()["id"]
    m = client.post("/api/models/register", headers=admin, json={**REG, "product_id": other}).json()
    assert client.patch(f"/api/products/{product_id}", headers=admin, json={"patchcore_model_id": m["id"]}).status_code == 422
    # even if forced in the DB, the registry refuses an incompatible model
    db = SessionLocal()
    p = db.get(Product, product_id)
    p.patchcore_model_id = m["id"]
    db.commit(); db.close()
    r = do_inspect(client, inspector, product_id, "good", mode="real")
    assert r.status_code == 409 and "compatibility" in str(r.json()["detail"]["reasons"])


class StubRegistry:
    """Deterministic mock model outputs (no weights involved)."""
    def __init__(self, score, classifier=None):
        class PC:
            def predict(_, rgb):
                h, w = rgb.shape[:2]
                hm = np.zeros((32, 32), np.float32)
                hm[8:16, 8:24] = 0.95
                return PatchCoreOutput(score=score, raw_score=score * 10, heatmap=hm)
        self.models = RealModels(PC(), classifier, "mock-pc:0.0")
    def require_ready(self, db, product):
        return self.models


class MockClassifierRuntime:
    def __init__(self, logits): self.logits = logits
    def run(self, x): return {"o": np.array([self.logits], np.float32)}


def _processed():
    return ImagePreprocessor(128).process(Image.open(__import__("io").BytesIO(png("obvious_defect"))))


@pytest.mark.parametrize("score,expected", [(0.1, Decision.PASS), (0.5, Decision.REVIEW), (0.9, Decision.FAIL)])
def test_engine_with_mock_patchcore(score, expected):
    eng = InspectionEngine(registry=StubRegistry(score))
    db = SessionLocal(); p = db.query(Product).first()
    r = eng.run(db, p, _processed(), "abc", "real")
    assert r.decision == expected and r.simulated is False and r.mode == "real" and r.boxes
    assert r.defect_class == ("unclassified_anomaly" if expected != Decision.PASS else None)
    db.close()


def test_engine_classifier_known_and_unknown():
    meta = {"class_names": ["scratch", "crack"], "input_size": [32, 32], "min_confidence": 0.6}
    known = ClassifierAdapter(MockClassifierRuntime([6.0, 0.0]), meta)
    unknown = ClassifierAdapter(MockClassifierRuntime([0.1, 0.0]), meta)
    db = SessionLocal(); p = db.query(Product).first()
    r1 = InspectionEngine(registry=StubRegistry(0.9, known)).run(db, p, _processed(), "abc", "real")
    r2 = InspectionEngine(registry=StubRegistry(0.9, unknown)).run(db, p, _processed(), "abc", "real")
    assert r1.defect_class == "scratch" and r1.confidence > 0.9
    assert r2.defect_class == "unknown_defect" and r2.confidence < 0.6
    db.close()


def test_real_engine_never_falls_back():
    class Broken:
        def require_ready(self, db, p): raise ModelNotReadyError(["no model"])
    db = SessionLocal(); p = db.query(Product).first()
    with pytest.raises(ModelNotReadyError):
        InspectionEngine(registry=Broken()).run(db, p, _processed(), "abc", "real")
    db.close()
