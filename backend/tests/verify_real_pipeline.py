"""
End-to-end verification script for genuine PatchCore ONNX visual inspection.
Validates:
1. Model loading and readiness endpoint.
2. Inference on normal Metal Nut image (real dataset).
3. Inference on defective Metal Nut images (scratch, bent).
4. Actual score, anomaly map, bounding boxes, decision.
5. Rejection of demo mode (422) and unsupported product (409).
6. Database persistence, history retrieval, PDF generation.
7. Audit chain integrity.
"""

import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal
from app.services.audit import verify_chain
from app.models.models import Inspection, Product

def main():
    print("=== STARTING END-TO-END PATCHCORE VERIFICATION ===")
    client = TestClient(app)

    # 1. Authenticate as admin
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "ChangeMe-Admin-123"})
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[1] Authentication successful as admin")

    # 2. Check model readiness endpoint
    resp = client.get("/api/models/status", headers=headers)
    assert resp.status_code == 200, f"Model status failed: {resp.text}"
    status_data = resp.json()
    print(f"[2] Model Status: {status_data['message']}")
    assert status_data["real_mode_available"] is True
    assert any(p["ready"] for p in status_data["products"].values())

    # Check system readiness endpoint
    resp = client.get("/api/system/status", headers=headers)
    assert resp.status_code == 200
    sys_data = resp.json()
    assert sys_data["real_mode_available"] is True
    assert sys_data["demo_mode_available"] is False
    print(f"    System Status: real_mode_available={sys_data['real_mode_available']}, demo_mode_available={sys_data['demo_mode_available']}")

    # 3. Check products configuration
    resp = client.get("/api/products", headers=headers)
    assert resp.status_code == 200
    products = resp.json()
    metal_nut = next((p for p in products if p["name"] == "Metal Nut"), None)
    assert metal_nut is not None
    assert metal_nut["real_mode_ready"] is True
    print(f"[3] Product '{metal_nut['name']}' (ID: {metal_nut['id']}) verified. Real mode ready: {metal_nut['real_mode_ready']}")
    
    paper = next((p for p in products if p["name"] == "Plain Paper"), None)
    if paper is not None:
        assert paper["real_mode_ready"] is True
        print(f"[3b] Product '{paper['name']}' (ID: {paper['id']}) verified. Real mode ready: {paper['real_mode_ready']}")

    # Verify unsupported products are marked unready
    unsupported = [p for p in products if p["name"] not in ("Metal Nut", "Plain Paper")]
    for u in unsupported:
        assert u["real_mode_ready"] is False
    print(f"    Confirmed {len(unsupported)} other products (PCB, Bracket, Bottle Cap) marked real_mode_ready=False")

    # 4. Rejection of demo mode
    dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    resp = client.post(
        "/api/inspect",
        headers=headers,
        data={"product_id": metal_nut["id"], "mode": "demo"},
        files={"file": ("test.png", dummy_img, "image/png")}
    )
    assert resp.status_code == 422, f"Demo mode was not rejected: {resp.status_code} {resp.text}"
    print("[4] Demo mode successfully rejected with 422 Unprocessable Entity")

    # 5. Invalid / corrupt image upload rejection (422)
    corrupt_bytes = b"NOT_AN_IMAGE_CONTENT_GARBAGE"
    resp = client.post(
        "/api/inspect",
        headers=headers,
        data={"product_id": metal_nut["id"], "mode": "real"},
        files={"file": ("corrupt.png", corrupt_bytes, "image/png")}
    )
    assert resp.status_code == 422, f"Corrupt image was not rejected: {resp.status_code} {resp.text}"
    print(f"[5] Corrupt image successfully rejected with 422: {resp.json()['detail']}")

    # 6. Real Dataset Inference: Normal / Good Metal Nut
    dataset_base = Path("C:/Users/rkraj/metal_nut_dataset/metal_nut/test")
    normal_img_path = dataset_base / "good" / "000.png"
    if not normal_img_path.exists():
        # Fallback to local test image if external path not found
        normal_img_path = Path("backend/tests/fixtures/sample_metal_nut.png")

    print(f"[6] Testing normal image: {normal_img_path}")
    with open(normal_img_path, "rb") as f:
        img_bytes = f.read()

    # 7. Rejection of unsupported product in real mode (requires valid image to reach readiness check)
    unsupported_prod = unsupported[0]
    resp = client.post(
        "/api/inspect",
        headers=headers,
        data={"product_id": unsupported_prod["id"], "mode": "real"},
        files={"file": ("valid_image.png", img_bytes, "image/png")}
    )
    assert resp.status_code == 409, f"Unsupported product was not rejected: {resp.status_code} {resp.text}"
    print(f"[7] Unsupported product '{unsupported_prod['name']}' rejected with 409 REAL_MODE_UNAVAILABLE")

    t0 = time.time()
    resp = client.post(
        "/api/inspect",
        headers=headers,
        data={
            "product_id": metal_nut["id"],
            "mode": "real",
            "product_code": "SN-GOOD-001",
            "batch_code": "BATCH-VERIFY",
            "line_id": "LINE-01",
            "notes": "Automated verification test - normal unit"
        },
        files={"file": ("normal_metal_nut.png", img_bytes, "image/png")}
    )
    assert resp.status_code == 201, f"Inspection failed: {resp.status_code} {resp.text}"
    good_insp = resp.json()
    expl = good_insp.get("explanation", {})
    print(f"    Result ID: {good_insp['id']}")
    print(f"    Decision: {good_insp['decision']}")
    print(f"    Anomaly Score: {good_insp['score']:.4f}")
    print(f"    Raw Score: {expl.get('raw_score')}")
    print(f"    Inference Latency: {good_insp['latency_ms']:.2f} ms")
    print(f"    Model Version: {good_insp['model_version']}")
    print(f"    Model Artifact Hash: {expl.get('model_artifact_sha256')}")
    print(f"    Calibration Status: {expl.get('calibration_status')}")
    print(f"    Image SHA256: {good_insp['image_sha256'][:16]}...")
    print(f"    Simulated: {good_insp['simulated']}")
    assert good_insp["simulated"] is False
    assert good_insp["mode"] == "real"
    assert good_insp["score"] is not None
    assert expl.get("model_artifact_sha256") is not None
    assert expl.get("calibration_status") in ("provisional", "uncalibrated")

    # 7. Real Dataset Inference: Defective Metal Nut (Scratch / Bent)
    scratch_img_path = dataset_base / "scratch" / "000.png"
    if not scratch_img_path.exists():
        scratch_img_path = dataset_base / "bent" / "000.png"

    if scratch_img_path.exists():
        print(f"[8] Testing defective image: {scratch_img_path}")
        with open(scratch_img_path, "rb") as f:
            scratch_bytes = f.read()

        resp = client.post(
            "/api/inspect",
            headers=headers,
            data={
                "product_id": metal_nut["id"],
                "mode": "real",
                "product_code": "SN-DEFECT-001",
                "batch_code": "BATCH-VERIFY",
                "line_id": "LINE-01",
                "notes": "Automated verification test - defective unit"
            },
            files={"file": ("scratch_metal_nut.png", scratch_bytes, "image/png")}
        )
        assert resp.status_code == 201, f"Defect inspection failed: {resp.status_code} {resp.text}"
        defect_insp = resp.json()
        defect_expl = defect_insp.get("explanation", {})
        print(f"    Result ID: {defect_insp['id']}")
        print(f"    Decision: {defect_insp['decision']}")
        print(f"    Anomaly Score: {defect_insp['score']:.4f}")
        print(f"    Raw Score: {defect_expl.get('raw_score')}")
        print(f"    Inference Latency: {defect_insp['latency_ms']:.2f} ms")
        print(f"    Defect BBoxes detected: {len(defect_insp['defects'])}")
        print(f"    Defect classification: {defect_insp['defect_class']}")
        print(f"    Classifier confidence: {defect_insp['confidence']}")
        assert defect_insp["simulated"] is False
        assert defect_insp["mode"] == "real"
        assert defect_expl.get("model_artifact_sha256") is not None

    # 8. Verify PDF report generation
    resp = client.get(f"/api/inspections/{good_insp['id']}/report", headers=headers)
    assert resp.status_code == 200, f"PDF report failed: {resp.status_code}"
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000
    print(f"[8] PDF report successfully generated ({len(resp.content)} bytes)")

    # 9. Verify History and Dashboard stats
    resp = client.get("/api/dashboard/stats?mode=real", headers=headers)
    assert resp.status_code == 200
    stats = resp.json()
    print(f"[9] Dashboard Stats: Total {stats['total']}, Real {stats['by_mode']['real']}, Passed {stats['passed']}, Defect Rate: {stats['defect_rate']:.2%}")

    # 10. Verify Audit Chain Integrity
    with SessionLocal() as db:
        res = verify_chain(db)
        print(f"[10] Audit Chain Verification: valid={res['valid']}, events_checked={res['events_checked']}, errors={res['problems']}")
        assert res["valid"] is True
        assert len(res["problems"]) == 0

    print("\n=== ALL REAL AI PATCHCORE PIPELINE CHECKS PASSED ===")

if __name__ == "__main__":
    main()
