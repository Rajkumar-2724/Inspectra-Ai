import sqlalchemy as sa

from app.database.session import SessionLocal
from app.models import AuditEvent, Inspection, Product
from tests.conftest import do_inspect, png


def _review_item(client, inspector, pid):
    db = SessionLocal()
    p = db.get(Product, pid)
    p.review_threshold, p.fail_threshold = 0.40, 0.90
    db.commit()
    db.close()
    return do_inspect(client, inspector, pid).json()


def test_review_workflow_preserves_ai_decision(client, inspector, reviewer, product_id):
    i = _review_item(client, inspector, product_id)
    pend = client.get("/api/reviews/pending", headers=reviewer).json()
    assert [x["id"] for x in pend] == [i["id"]]
    assert client.post(f"/api/reviews/{i['id']}/decision", headers=inspector, json={"decision": "approve"}).status_code == 403
    assert client.post(f"/api/reviews/{i['id']}/decision", headers=reviewer, json={"decision": "reject", "comment": " "}).status_code == 422
    r = client.post(f"/api/reviews/{i['id']}/decision", headers=reviewer, json={"decision": "reject", "comment": "Visible crack"})
    assert r.status_code == 200
    j = r.json()
    assert j["decision"] == "REVIEW" and j["score"] == i["score"]  # original AI output untouched
    assert j["final_decision"] == "FAIL" and j["review_status"] == "REVIEWED"
    assert j["reviews"][0]["reviewer_name"] == "Reviewer" and j["reviews"][0]["comment"] == "Visible crack"
    assert client.get("/api/reviews/pending", headers=reviewer).json() == []
    assert client.post(f"/api/reviews/{i['id']}/decision", headers=reviewer, json={"decision": "approve"}).status_code == 409


def test_review_approve_and_reinspect(client, inspector, reviewer, product_id):
    a, b = _review_item(client, inspector, product_id), _review_item(client, inspector, product_id)
    assert client.post(f"/api/reviews/{a['id']}/decision", headers=reviewer, json={"decision": "approve"}).json()["final_decision"] == "PASS"
    r = client.post(f"/api/reviews/{b['id']}/decision", headers=reviewer, json={"decision": "reinspect", "comment": "retake"}).json()
    assert r["review_status"] == "REINSPECT" and r["final_decision"] is None


def test_batch_partial_failure_and_retry(client, inspector, product_id):
    b = client.post("/api/batches", headers=inspector, json={"product_id": product_id, "batch_code": "BATCH-1", "line_id": "L2", "mode": "real"}).json()
    files = [("files", ("a.png", png("good", 1), "image/png")), ("files", ("b.png", png("obvious_defect", 2), "image/png")),
             ("files", ("c.png", png("subtle_defect", 3), "image/png")), ("files", ("bad.png", b"garbage", "image/png"))]
    r = client.post(f"/api/batches/{b['id']}/inspect", headers=inspector, files=files)
    assert r.status_code == 202
    st = client.get(f"/api/batches/{b['id']}/status", headers=inspector).json()
    assert st["finished"] and st["job_counts"]["DONE"] == 3 and st["job_counts"]["FAILED"] == 1 and st["progress"] == 1.0
    full = client.get(f"/api/batches/{b['id']}", headers=inspector).json()
    assert sum(full["counts"].values()) == 3 and any(j["error"] for j in full["jobs"] if j["status"] == "FAILED")
    items = client.get(f"/api/batches/{b['id']}/inspections", headers=inspector).json()
    assert len(items) == 3 and all(x["batch_code"] == "BATCH-1" and x["line_id"] == "L2" for x in items)
    rp = client.get(f"/api/batches/{b['id']}/report", headers=inspector)
    assert rp.status_code == 200 and rp.content[:5] == b"%PDF-"
    assert "BATCH-1" in client.get(f"/api/batches/{b['id']}/export/csv", headers=inspector).text
    client.post(f"/api/batches/{b['id']}/retry", headers=inspector)
    st = client.get(f"/api/batches/{b['id']}/status", headers=inspector).json()
    assert st["job_counts"]["DONE"] == 3 and st["job_counts"]["FAILED"] == 1


def test_batch_real_mode_refused_without_models(client, inspector):
    db = SessionLocal()
    unready = Product(name="Unready Prod Batch", category="Other", review_threshold=0.4, fail_threshold=0.7)
    db.add(unready)
    db.commit()
    uid = unready.id
    db.close()
    r = client.post("/api/batches", headers=inspector, json={"product_id": uid, "batch_code": "R1", "mode": "real"})
    assert r.status_code == 409


def test_audit_chain_valid_and_events(client, admin, inspector, reviewer, product_id):
    assert client.get("/api/audit/verify", headers=admin).json()["valid"] is True
    for _ in range(2):
        do_inspect(client, inspector, product_id)
    i = _review_item(client, inspector, product_id)
    client.post(f"/api/reviews/{i['id']}/decision", headers=reviewer, json={"decision": "approve"})
    v = client.get("/api/audit/verify", headers=admin).json()
    assert v["valid"] and v["events_checked"] == 4
    ev = client.get("/api/audit/events", headers=inspector).json()
    assert ev["total"] == 4
    items = sorted(ev["items"], key=lambda e: e["seq"])
    assert items[0]["prev_hash"] == "0" * 64
    for a, b in zip(items, items[1:]):
        assert b["prev_hash"] == a["record_hash"]
    assert {e["event_type"] for e in items} == {"INSPECTION", "REVIEW"}
    assert client.delete("/api/audit/events", headers=admin).status_code == 405
    assert client.put("/api/audit/events", headers=admin, json={}).status_code == 405


def test_hash_formula():
    import hashlib
    from app.services.audit import canonical_json, compute_hash
    p = {"b": 1, "a": [2, 1]}
    assert canonical_json(p) == '{"a":[2,1],"b":1}'
    assert compute_hash("abc", canonical_json(p)) == hashlib.sha256(("abc" + '{"a":[2,1],"b":1}').encode()).hexdigest()


def _setup_chain(client, inspector, pid):
    for _ in range(3):
        do_inspect(client, inspector, pid)


def test_tamper_audit_payload(client, admin, inspector, product_id):
    _setup_chain(client, inspector, product_id)
    db = SessionLocal()
    ev = db.query(AuditEvent).filter_by(seq=2).one()
    ev.payload_json = ev.payload_json.replace('"anomaly_score":', '"anomaly_score":999.')
    db.commit(); db.close()
    v = client.get("/api/audit/verify", headers=admin).json()
    assert v["valid"] is False and any(p["seq"] == 2 for p in v["problems"])


def test_tamper_inspection_row(client, admin, inspector, product_id):
    _setup_chain(client, inspector, product_id)
    db = SessionLocal()
    row = db.query(Inspection).filter_by(id=2).one()
    row.score = 0.999999
    db.commit(); db.close()
    v = client.get("/api/audit/verify", headers=admin).json()
    assert v["valid"] is False and any("differs" in p["problem"] for p in v["problems"])


def test_tamper_deleted_audit_record(client, admin, inspector, product_id):
    _setup_chain(client, inspector, product_id)
    db = SessionLocal()
    db.query(AuditEvent).filter_by(seq=2).delete()
    db.commit(); db.close()
    assert client.get("/api/audit/verify", headers=admin).json()["valid"] is False

