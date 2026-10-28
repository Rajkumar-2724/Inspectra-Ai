import base64
import hashlib
import io
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.ai.decision_engine import DecisionEngine
from app.ai.explainability import ExplainabilityService
from app.ai.inspection_engine import InspectionEngine
from app.ai.localization import HeatmapProcessor, draw_annotations, draw_boxes, extract_region_crop
from app.ai.preprocessing import ImagePreprocessor, validate_image_bytes
from app.core.config import get_settings
from app.models import (Decision, Inspection, InspectionBatch, InspectionDefect, InspectionImage, Mode,
                        ModelVersion, Product, ReviewStatus, User)
from app.schemas.schemas import DefectOut, InspectionOut
from app.services import audit
from app.services.events import hub
from app.utils.time import utcnow

engine = InspectionEngine()
explainer = ExplainabilityService()
heat = HeatmapProcessor()


class InspectionError(ValueError):
    pass


def storage_file(rel: str) -> Path:
    """Resolve a stored relative path, refusing anything outside the storage root."""
    root = get_settings().storage_path
    p = (root / rel).resolve()
    if not p.is_relative_to(root):
        raise InspectionError("Invalid storage path")
    return p


def _save(arr: np.ndarray, path: Path) -> tuple[int, int]:
    Image.fromarray(arr).save(path, "PNG")
    return arr.shape[1], arr.shape[0]


def run_inspection(db: Session, *, user_id: int | None, product: Product, data: bytes, mode: str = "real",
                   scenario: str | None = None, product_code: str = "", batch: InspectionBatch | None = None,
                   batch_code: str = "", line_id: str = "", notes: str = "",
                   created_at: datetime | None = None) -> Inspection:
    s = get_settings()
    if product.archived:
        raise InspectionError("Product is archived")
    DecisionEngine.validate_thresholds(product.review_threshold, product.fail_threshold)
    pil, ext = validate_image_bytes(data, s.MAX_UPLOAD_MB * 1024 * 1024)
    sha = hashlib.sha256(data).hexdigest()
    processed = ImagePreprocessor(s.MAX_IMAGE_SIDE).process(pil)
    res = engine.run(db, product, processed, sha, mode="real")  # may raise ModelNotReadyError (no fallback)

    rgb = processed.rgb
    hm_color = heat.colorize(res.heatmap)
    overlay = heat.overlay(rgb, res.heatmap)
    annotated = draw_annotations(rgb, res.boxes, draw_ellipses=True, draw_boxes=False, draw_badges=True)
    overlay_boxes = draw_annotations(overlay, res.boxes, draw_ellipses=True, draw_boxes=False, draw_badges=True)
    ref_path = storage_file(product.reference_image_path) if product.reference_image_path else None
    ref_patch = explainer.reference_patch(ref_path, (rgb.shape[1], rgb.shape[0]), res.boxes)

    loc_status = res.boxes[0].get("localization_status", "provisional") if res.boxes else "provisional"
    loc_thresh = res.boxes[0].get("localization_threshold", product.review_threshold) if res.boxes else product.review_threshold

    uid = str(uuid.uuid4())
    rel_dir = Path("inspections") / uid
    out_dir = storage_file(str(rel_dir))

    crop_files = {}
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        # Extract and save zoomed crops for each detected defect region
        for idx, b in enumerate(res.boxes, start=1):
            crop_kind = f"crop_{b.get('id', idx)}"
            crop_arr = extract_region_crop(rgb, b, target_size=160)
            crop_fname = f"{crop_kind}.png"
            crop_files[crop_kind] = (crop_fname, _save(crop_arr, out_dir / crop_fname))
            buf = io.BytesIO()
            Image.fromarray(crop_arr).save(buf, format="JPEG", quality=85)
            b["crop_data"] = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
            b["crop_kind"] = crop_kind

        explanation = explainer.explain(
            score=res.score,
            review=product.review_threshold,
            fail=product.fail_threshold,
            decision=res.decision,
            boxes=res.boxes,
            simulated=False,
            mode="real",
            scenario=None,
            reference_available=ref_patch is not None,
            localization_status=loc_status,
            localization_threshold=loc_thresh,
        )

        model_sha = None
        if product.patchcore_model_id:
            mv = db.get(ModelVersion, product.patchcore_model_id)
            if mv:
                model_sha = mv.file_sha256
        explanation["model_artifact_sha256"] = model_sha
        explanation["raw_score"] = round(res.raw_score, 6)
        explanation["calibration_status"] = loc_status
        explanation["preprocessing"] = {
            "original_size": list(processed.original_size),
            "processed_size": [rgb.shape[1], rgb.shape[0]],
            "scale": round(processed.scale, 4),
            "orientation": "EXIF orientation applied",
        }

        (out_dir / f"original.{ext}").write_bytes(data)
        files = {"original": (f"original.{ext}", pil.size)}
        for kind, arr in (("processed", rgb), ("heatmap", hm_color), ("overlay", overlay_boxes), ("annotated", annotated)):
            files[kind] = (f"{kind}.png", _save(arr, out_dir / f"{kind}.png"))
        if ref_patch is not None:
            files["reference_patch"] = ("reference_patch.png", _save(ref_patch, out_dir / "reference_patch.png"))
        files.update(crop_files)

        insp = Inspection(
            uid=uid, product_id=product.id, product_code=product_code[:64], batch_id=batch.id if batch else None,
            batch_code=(batch.batch_code if batch else batch_code)[:64], line_id=(batch.line_id if batch and not line_id else line_id)[:64],
            mode=Mode.real, simulated=False, scenario=None, score=round(res.score, 6),
            decision=res.decision, defect_class=res.defect_class, confidence=res.confidence,
            review_threshold=product.review_threshold, fail_threshold=product.fail_threshold,
            model_version=res.model_version, latency_ms=round(res.latency_ms, 2), notes=notes[:2000], image_sha256=sha,
            image_width=processed.original_size[0], image_height=processed.original_size[1],
            review_status=ReviewStatus.PENDING if res.decision == Decision.REVIEW else ReviewStatus.NONE,
            explanation_json=json.dumps(explanation), created_by=user_id, created_at=created_at or utcnow())
        for b in res.boxes:
            insp.defects.append(InspectionDefect(x=b["x"], y=b["y"], w=b["w"], h=b["h"], area=b["area"],
                                                 peak_score=b["peak_score"], label=b["label"], confidence=b["confidence"]))
        for kind, (fname, size) in files.items():
            insp.images.append(InspectionImage(kind=kind, path=str(rel_dir / fname).replace("\\", "/"), width=size[0], height=size[1]))
        db.add(insp)
        db.flush()
        audit.append_event(db, "INSPECTION", insp.id, audit.inspection_payload(insp), created_at=insp.created_at)
        db.commit()
    except Exception:
        db.rollback()
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    hub.publish({"type": "inspection", "id": insp.id, "decision": insp.decision.value, "mode": insp.mode.value})
    return insp


def to_out(i: Inspection) -> InspectionOut:
    try:
        expl = json.loads(i.explanation_json or "{}")
    except ValueError:
        expl = {}

    # Enrich defect list with circle/ellipse geometry from stored explanation
    regions_map = {r.get("id"): r for r in expl.get("regions", []) if isinstance(r, dict)}
    defect_outs: list[DefectOut] = []
    for idx, d in enumerate(i.defects, start=1):
        reg = regions_map.get(idx) or regions_map.get(d.id)
        center = reg.get("center") if reg else [d.x + d.w / 2.0, d.y + d.h / 2.0]
        axes = reg.get("axes") if reg else [d.w / 2.0, d.h / 2.0]
        shape = reg.get("shape", "ellipse") if reg else "ellipse"
        angle = reg.get("angle", 0.0) if reg else 0.0
        crop_kind = reg.get("crop_kind", f"crop_{idx}") if reg else f"crop_{idx}"

        defect_outs.append(DefectOut(
            id=d.id, x=d.x, y=d.y, w=d.w, h=d.h, area=d.area, peak_score=d.peak_score,
            label=d.label, confidence=d.confidence, region_id=idx, shape=shape,
            center_x=round(float(center[0]), 2), center_y=round(float(center[1]), 2),
            radius_x=round(float(axes[0]), 2), radius_y=round(float(axes[1]), 2),
            angle=round(float(angle), 2), crop_kind=crop_kind
        ))

    return InspectionOut(
        id=i.id, uid=i.uid, product_id=i.product_id, product_name=i.product.name, product_category=i.product.category,
        product_code=i.product_code, batch_id=i.batch_id, batch_code=i.batch_code, line_id=i.line_id, mode=i.mode.value,
        simulated=i.simulated, scenario=i.scenario, score=i.score, decision=i.decision, defect_class=i.defect_class,
        confidence=i.confidence, review_threshold=i.review_threshold, fail_threshold=i.fail_threshold,
        model_version=i.model_version, latency_ms=i.latency_ms, notes=i.notes, image_sha256=i.image_sha256,
        image_width=i.image_width, image_height=i.image_height,
        review_status=i.review_status, final_decision=i.final_decision, explanation=expl,
        defects=defect_outs, reviews=[r for r in i.reviews], images=[im.kind for im in i.images],
        created_at=i.created_at)
