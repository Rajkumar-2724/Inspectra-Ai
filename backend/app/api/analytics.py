"""Dashboard + analytics. Computed with pandas from persisted inspections only.
No accuracy/precision/recall/F1/AUROC is ever invented: metrics need EvaluationLabel rows."""
from datetime import timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models import EvaluationLabel, Inspection, Product, ReviewStatus, Role, User
from app.schemas.schemas import GroundTruthIn
from app.services.inspection_service import to_out
from app.utils.time import utcnow

router = APIRouter(prefix="/api", tags=["analytics"])
NOT_EVALUATED = "Not evaluated — ground-truth labels required."


def _df(db: Session, mode: str | None, days: int | None, product_id: int | None = None) -> pd.DataFrame:
    q = select(Inspection.id, Inspection.created_at, Inspection.decision, Inspection.mode, Inspection.product_id, Inspection.defect_class,
               Inspection.latency_ms, Inspection.batch_code, Inspection.line_id, Inspection.review_status, Inspection.final_decision,
               Inspection.score)
    if mode in ("demo", "real"):
        q = q.where(Inspection.mode == mode)
    if days:
        q = q.where(Inspection.created_at >= utcnow() - timedelta(days=days))
    if product_id:
        q = q.where(Inspection.product_id == product_id)
    rows = db.execute(q).all()
    df = pd.DataFrame(rows, columns=["id", "created_at", "decision", "mode", "product_id", "defect_class", "latency_ms", "batch_code",
                                     "line_id", "review_status", "final_decision", "score"])
    if not df.empty:
        for c in ("decision", "mode", "review_status", "final_decision"):
            df[c] = df[c].map(lambda v: v.value if hasattr(v, "value") else v)
        df["day"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d")
    return df


def _names(db: Session) -> dict[int, str]:
    return {p.id: p.name for p in db.execute(select(Product)).scalars()}


def _dist(df: pd.DataFrame) -> dict[str, int]:
    return {k: int((df["decision"] == k).sum()) if not df.empty else 0 for k in ("PASS", "REVIEW", "FAIL")}


@router.get("/dashboard/stats")
def stats(mode: str | None = Query(None, pattern="^(demo|real)$"), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _df(db, mode, None)
    names = _names(db)
    total = len(df)
    d = _dist(df)
    by_mode = {m: int((df["mode"] == m).sum()) if total else 0 for m in ("demo", "real")}
    by_prod = []
    if total:
        for pid, g in df.groupby("product_id"):
            by_prod.append({"product": names.get(pid, str(pid)), "total": len(g), **_dist(g)})
    return {"total": total, "passed": d["PASS"], "review": d["REVIEW"], "failed": d["FAIL"],
            "pending_reviews": int((df["review_status"] == ReviewStatus.PENDING.value).sum()) if total else 0,
            "defect_rate": round((d["FAIL"] + d["REVIEW"]) / total, 4) if total else None,
            "avg_latency_ms": round(float(df["latency_ms"].mean()), 2) if total else None,
            "by_mode": by_mode, "by_product": by_prod, "has_demo_data": by_mode["demo"] > 0}


@router.get("/dashboard/trends")
def trends(days: int = Query(14, ge=1, le=365), mode: str | None = Query(None, pattern="^(demo|real)$"),
           _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _df(db, mode, days)
    if df.empty:
        return {"daily": [], "distribution": _dist(df), "defect_categories": [], "latency": []}
    daily = []
    for day, g in df.groupby("day"):
        daily.append({"day": day, "total": len(g), **{k.lower(): v for k, v in _dist(g).items()},
                      "avg_latency_ms": round(float(g["latency_ms"].mean()), 2)})
    cats = df[df["defect_class"].notna()].groupby("defect_class").size().sort_values(ascending=False)
    return {"daily": daily, "distribution": _dist(df),
            "defect_categories": [{"defect": k, "count": int(v)} for k, v in cats.items()],
            "latency": [{"day": r["day"], "avg_latency_ms": r["avg_latency_ms"]} for r in daily]}


@router.get("/dashboard/recent")
def recent(limit: int = Query(8, ge=1, le=50), mode: str | None = Query(None, pattern="^(demo|real)$"),
           _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Inspection).order_by(Inspection.id.desc()).limit(limit)
    if mode:
        q = q.where(Inspection.mode == mode)
    return [to_out(i) for i in db.execute(q).scalars().all()]


@router.get("/analytics/defects")
def defects(days: int = Query(30, ge=1, le=365), mode: str | None = Query(None, pattern="^(demo|real)$"), product_id: int | None = None,
            _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _df(db, mode, days, product_id)
    names = _names(db)
    empty = {"total": 0, "counts": [], "category_trends": [], "by_product": [], "by_batch": [], "by_line": [], "regions": [],
             "review_rate": None, "evaluation": {"evaluated": False, "message": NOT_EVALUATED}}
    if df.empty:
        return empty
    flagged = df[df["decision"] != "PASS"]
    counts = df[df["defect_class"].notna()].groupby("defect_class").size().sort_values(ascending=False)
    cat_trend = []
    for (day, cls), n in df[df["defect_class"].notna()].groupby(["day", "defect_class"]).size().items():
        cat_trend.append({"day": day, "defect": cls, "count": int(n)})
    by_product = [{"product": names.get(pid, str(pid)), "total": len(g), "defects": int((g["decision"] != "PASS").sum()),
                   "by_class": g[g["defect_class"].notna()].groupby("defect_class").size().to_dict()} for pid, g in df.groupby("product_id")]
    def rate(col):
        out = []
        for key, g in df[df[col] != ""].groupby(col):
            out.append({col: key, "total": len(g), "flagged": int((g["decision"] != "PASS").sum()),
                        "defect_rate": round(float((g["decision"] != "PASS").mean()), 4), **{k.lower(): v for k, v in _dist(g).items()}})
        return sorted(out, key=lambda r: -r["defect_rate"])
    # most frequently flagged regions: 3x3 grid of defect-box centres in normalised image coordinates
    from app.models import InspectionDefect
    ids = [int(i) for i in df["id"]]
    grid = [[0] * 3 for _ in range(3)]
    for d, iw, ih in db.execute(select(InspectionDefect, Inspection.image_width, Inspection.image_height).join(Inspection).where(InspectionDefect.inspection_id.in_(ids))).all():
        pw = max(iw, 1)
        # boxes are in processed-image coordinates; normalise using processed size ≈ max_side scaling
        scale = min(1.0, 640 / max(iw, ih, 1))
        w_p, h_p = max(1, round(iw * scale)), max(1, round(ih * scale))
        gx, gy = min(2, int((d.x + d.w / 2) / w_p * 3)), min(2, int((d.y + d.h / 2) / h_p * 3))
        grid[gy][gx] += 1
    return {"total": len(df), "counts": [{"defect": k, "count": int(v)} for k, v in counts.items()], "category_trends": cat_trend,
            "by_product": by_product, "by_batch": rate("batch_code"), "by_line": rate("line_id"), "regions": grid,
            "review_rate": round(float((df["decision"] == "REVIEW").mean()), 4), "flagged": len(flagged),
            "evaluation": _evaluation(db, mode)}


def _evaluation(db: Session, mode: str | None) -> dict:
    q = select(Inspection.decision, Inspection.mode, EvaluationLabel.ground_truth).join(EvaluationLabel, EvaluationLabel.inspection_id == Inspection.id)
    if mode:
        q = q.where(Inspection.mode == mode)
    rows = db.execute(q).all()
    if not rows:
        return {"evaluated": False, "message": NOT_EVALUATED, "labeled_samples": 0}
    tp = sum(1 for d, _, g in rows if g == "defective" and d.value != "PASS")
    fn = sum(1 for d, _, g in rows if g == "defective" and d.value == "PASS")  # false pass
    fp = sum(1 for d, _, g in rows if g == "good" and d.value == "FAIL")  # false fail
    tn = sum(1 for d, _, g in rows if g == "good" and d.value != "FAIL")
    return {"evaluated": True, "labeled_samples": len(rows), "false_pass": fn, "false_fail": fp, "true_flagged": tp, "true_good": tn,
            "false_pass_rate": round(fn / (fn + tp), 4) if (fn + tp) else None, "false_fail_rate": round(fp / (fp + tn), 4) if (fp + tn) else None,
            "includes_demo_samples": any(m.value == "demo" for _, m, _ in rows),
            "note": "Computed only from verified labels. REVIEW counts as flagged for false-pass; only FAIL counts as false-fail."}


@router.post("/analytics/ground-truth", status_code=201)
def add_ground_truth(body: GroundTruthIn, user: User = Depends(require_roles(Role.reviewer)), db: Session = Depends(get_db)):
    """Evaluation-data schema: attach verified ground truth to an inspection so real metrics can be computed."""
    if not db.get(Inspection, body.inspection_id):
        raise HTTPException(404, "Inspection not found")
    row = db.execute(select(EvaluationLabel).where(EvaluationLabel.inspection_id == body.inspection_id)).scalar_one_or_none()
    if row:
        row.ground_truth, row.true_defect_class, row.labeled_by = body.ground_truth, body.true_defect_class, user.id
    else:
        db.add(EvaluationLabel(inspection_id=body.inspection_id, ground_truth=body.ground_truth, true_defect_class=body.true_defect_class, labeled_by=user.id))
    db.commit()
    return {"ok": True}


@router.get("/analytics/trends")
def analytics_trends(days: int = Query(30, ge=1, le=365), mode: str | None = Query(None, pattern="^(demo|real)$"),
                     _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _df(db, mode, days)
    if df.empty:
        return {"daily": []}
    out = []
    for day, g in df.groupby("day"):
        n = len(g)
        out.append({"day": day, "total": n, **{k.lower(): v for k, v in _dist(g).items()},
                    "defect_rate": round(float((g["decision"] != "PASS").mean()), 4), "review_rate": round(float((g["decision"] == "REVIEW").mean()), 4)})
    return {"daily": out}


@router.get("/analytics/latency")
def latency(days: int = Query(30, ge=1, le=365), mode: str | None = Query(None, pattern="^(demo|real)$"),
            _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _df(db, mode, days)
    if df.empty:
        return {"count": 0, "avg_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None, "daily": [], "by_mode": {}}
    s = df["latency_ms"]
    return {"count": len(df), "avg_ms": round(float(s.mean()), 2), "p50_ms": round(float(s.quantile(0.5)), 2),
            "p95_ms": round(float(s.quantile(0.95)), 2), "max_ms": round(float(s.max()), 2),
            "daily": [{"day": d, "avg_ms": round(float(g["latency_ms"].mean()), 2)} for d, g in df.groupby("day")],
            "by_mode": {m: round(float(g["latency_ms"].mean()), 2) for m, g in df.groupby("mode")},
            "note": "Latency is model/engine time only; demo-mode latency is not representative of real inference."}
