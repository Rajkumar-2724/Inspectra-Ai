import io

import pytest
from PIL import Image

from tests.conftest import do_inspect, png


import io

import pytest
from PIL import Image

from tests.conftest import do_inspect, png


def test_real_inference_execution(client, inspector, product_id):
    r = do_inspect(client, inspector, product_id)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["mode"] == "real" and j["simulated"] is False
    assert j["review_threshold"] == 0.4 and j["fail_threshold"] == 0.7
    assert j["model_version"].startswith("test-patchcore")
    assert "score" in j and isinstance(j["score"], float)
    assert j["decision"] in ("PASS", "REVIEW", "FAIL")


def test_real_inference_is_deterministic(client, inspector, product_id):
    a = do_inspect(client, inspector, product_id).json()
    b = do_inspect(client, inspector, product_id).json()
    assert a["score"] == b["score"] and a["image_sha256"] == b["image_sha256"]


def test_persistence_images_and_filters(client, inspector, product_id):
    i = do_inspect(client, inspector, product_id, product_code="SN-1", batch_code="B1", line_id="L1").json()
    got = client.get(f"/api/inspections/{i['id']}", headers=inspector).json()
    assert got["uid"] == i["uid"] and got["batch_code"] == "B1"
    imgs = client.get(f"/api/inspections/{i['id']}/images", headers=inspector).json()
    kinds = {x["kind"] for x in imgs}
    assert {"original", "processed", "heatmap", "overlay", "annotated"} <= kinds
    for k in kinds:
        r = client.get(f"/api/inspections/{i['id']}/images/{k}", headers=inspector)
        assert r.status_code == 200 and Image.open(io.BytesIO(r.content)).size[0] > 0
    assert client.get(f"/api/inspections/{i['id']}/images/../../etc", headers=inspector).status_code in (404, 422)
    page = client.get("/api/inspections", headers=inspector, params={"search": "SN-1"}).json()
    assert page["total"] == 1
    assert client.get("/api/inspections", headers=inspector, params={"mode": "real"}).json()["total"] == 1
    assert client.get("/api/inspections", headers=inspector, params={"decision": "BAD"}).status_code == 422


def test_invalid_uploads(client, inspector, product_id):
    assert do_inspect(client, inspector, product_id, data=b"not an image").status_code == 422
    assert do_inspect(client, inspector, product_id, data=b"").status_code == 422
    assert do_inspect(client, inspector, 9999).status_code == 404
    assert do_inspect(client, inspector, product_id, mode="demo").status_code == 422
    assert do_inspect(client, inspector, product_id, mode="bogus").status_code == 422
    assert client.get("/api/inspections", headers=inspector).json()["total"] == 0


def test_real_mode_refuses_without_models(client, inspector):
    from app.models import Product
    from app.database.session import SessionLocal
    db = SessionLocal()
    unready = Product(name="Unready Prod", category="Other", review_threshold=0.4, fail_threshold=0.7)
    db.add(unready)
    db.commit()
    uid = unready.id
    db.close()
    r = do_inspect(client, inspector, uid, mode="real")
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "REAL_MODE_UNAVAILABLE" and d["reasons"]
    assert client.get("/api/inspections", headers=inspector).json()["total"] == 0


def test_reports_and_csv(client, inspector, product_id):
    i = do_inspect(client, inspector, product_id, batch_code="B9").json()
    r = client.get(f"/api/inspections/{i['id']}/report", headers=inspector)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and len(r.content) > 5000
    c = client.get("/api/inspections/export/csv", headers=inspector)
    assert c.status_code == 200 and "anomaly_score" in c.text and "real" in c.text and "B9" in c.text


def test_dashboard_and_analytics(client, inspector, product_id):
    s = client.get("/api/dashboard/stats", headers=inspector).json()
    assert s["total"] == 0 and s["avg_latency_ms"] is None and s["defect_rate"] is None  # empty state
    a = client.get("/api/analytics/defects", headers=inspector).json()
    assert a["evaluation"]["evaluated"] is False and "ground-truth" in a["evaluation"]["message"]
    for _ in range(3):
        do_inspect(client, inspector, product_id)
    s = client.get("/api/dashboard/stats", headers=inspector).json()
    assert s["total"] == 3
    assert s["by_mode"]["real"] == 3
    t = client.get("/api/dashboard/trends", headers=inspector).json()
    assert t["daily"] and t["defect_categories"]
    assert client.get("/api/dashboard/recent", headers=inspector).json()
    assert client.get("/api/analytics/latency", headers=inspector).json()["count"] == 3
    assert client.get("/api/analytics/trends", headers=inspector).json()["daily"]


def test_ground_truth_metrics_only_from_labels(client, inspector, reviewer, product_id):
    a = do_inspect(client, inspector, product_id).json()
    b = do_inspect(client, inspector, product_id).json()
    assert client.post("/api/analytics/ground-truth", headers=inspector, json={"inspection_id": a["id"], "ground_truth": "good"}).status_code == 403
    client.post("/api/analytics/ground-truth", headers=reviewer, json={"inspection_id": a["id"], "ground_truth": "defective"})
    client.post("/api/analytics/ground-truth", headers=reviewer, json={"inspection_id": b["id"], "ground_truth": "defective"})
    ev = client.get("/api/analytics/defects", headers=inspector).json()["evaluation"]
    assert ev["evaluated"] and ev["labeled_samples"] == 2
    assert "accuracy" not in ev and "f1" not in ev


def test_product_crud_and_thresholds(client, admin, inspector):
    body = {"name": "Cap A", "category": "Bottle or cap", "defect_classes": ["Crack", "crack", "Bad Seal"], "review_threshold": 0.3, "fail_threshold": 0.6}
    p = client.post("/api/products", headers=admin, json=body)
    assert p.status_code == 201 and p.json()["defect_classes"] == ["crack", "bad_seal"]
    pid = p.json()["id"]
    assert client.post("/api/products", headers=admin, json=body).status_code == 409
    assert client.post("/api/products", headers=admin, json={**body, "name": "Bad", "review_threshold": 0.9}).status_code == 422
    assert client.patch(f"/api/products/{pid}", headers=admin, json={"review_threshold": 0.8}).status_code == 422
    assert client.patch(f"/api/products/{pid}", headers=inspector, json={"description": "x"}).status_code == 403
    assert client.patch(f"/api/products/{pid}", headers=admin, json={"review_threshold": 0.2, "fail_threshold": 0.5}).json()["fail_threshold"] == 0.5
    ref = client.post(f"/api/products/{pid}/reference-image", headers=admin, files={"file": ("r.png", png("good"), "image/png")})
    assert ref.status_code == 200 and ref.json()["has_reference_image"]
    # Cap A has no model assigned, so inspection is refused with 409
    assert do_inspect(client, inspector, pid).status_code == 409
    assert client.delete(f"/api/products/{pid}", headers=admin).json()["archived"] is True
    assert do_inspect(client, inspector, pid).status_code == 422
    assert pid not in [x["id"] for x in client.get("/api/products", headers=inspector).json()]

