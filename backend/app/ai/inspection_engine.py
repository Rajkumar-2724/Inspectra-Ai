"""Orchestrates genuine AI inference. Real ONNX model is the only inspection path."""
import time

from sqlalchemy.orm import Session

from app.ai.classifier_adapter import UNKNOWN_DEFECT
from app.ai.decision_engine import DecisionEngine
from app.ai.localization import DefectLocalizer, HeatmapProcessor, Region, map_regions_to_original
from app.ai.model_registry import ModelNotReadyError, ModelRegistry, registry as default_registry
from app.ai.preprocessing import ProcessedImage
from app.ai.types import EngineResult
from app.models.models import Decision, Product

UNCLASSIFIED = "unclassified_anomaly"


class InspectionEngine:
    def __init__(self, registry: ModelRegistry | None = None):
        self.registry = registry or default_registry
        self.heat, self.localizer = HeatmapProcessor(), DefectLocalizer()

    def run(self, db: Session, product: Product, processed: ProcessedImage, image_sha: str, mode: str = "real",
            scenario: str | None = None) -> EngineResult:
        if mode != "real":
            raise ValueError("Only 'real' inference mode is supported. Demo mode has been removed.")
        models = self.registry.require_ready(db, product)  # raises ModelNotReadyError, no fallback
        rgb = processed.rgb
        h, w = rgb.shape[:2]
        t0 = time.perf_counter()
        out = models.patchcore.predict(rgb)
        hm = self.heat.smooth(self.heat.resize(out.heatmap, (w, h)), 2.0)
        decision = DecisionEngine.decide(out.score, product.review_threshold, product.fail_threshold)

        # Retrieve pixel-level localization threshold and calibration status from metadata
        meta = getattr(models.patchcore, "meta", {})
        metrics = meta.get("metrics", {}) if isinstance(meta, dict) else {}
        loc_thresh = metrics.get("localization_threshold") or (meta.get("localization_threshold") if isinstance(meta, dict) else None)
        if loc_thresh is None:
            # Fall back to product review threshold as provisional pixel threshold on the global anomaly map
            loc_thresh = product.review_threshold
            loc_status = "uncalibrated"
        else:
            loc_status = meta.get("calibration_status", "provisional")

        raw_regions = self.localizer.locate(hm, loc_thresh)
        # Normal image protection: on PASS images with low anomaly score, do not force false defect regions
        if decision == Decision.PASS:
            raw_regions = [r for r in raw_regions if r.peak >= product.review_threshold]

        mapped_regions = map_regions_to_original(raw_regions, processed.scale, processed.original_size)

        boxes: list[dict] = []
        for r in mapped_regions:
            label, conf = UNCLASSIFIED, None
            if models.classifier is not None:
                # Classify using crop only if a compatible trained classifier exists
                res = models.classifier.classify(rgb[r.y:r.y + r.h, r.x:r.x + r.w])
                label, conf = (UNKNOWN_DEFECT if res.is_unknown else res.label), res.confidence
            r.label = label
            r.confidence = conf

            reg_dict = r.to_dict()
            reg_dict["localization_status"] = loc_status
            reg_dict["localization_threshold"] = round(loc_thresh, 4)
            boxes.append(reg_dict)

        latency = (time.perf_counter() - t0) * 1000
        top = boxes[0] if boxes else None
        flagged = decision != Decision.PASS
        notes = [f"Localization status: {loc_status} (threshold={loc_thresh:.3f})"]
        if models.classifier is None:
            notes.append("No defect classifier attached; localized anomalies labeled 'unclassified_anomaly'.")

        return EngineResult(mode="real", score=out.score, raw_score=out.raw_score, decision=decision, heatmap=hm,
                            boxes=boxes, defect_class=(top["label"] if top else UNCLASSIFIED) if flagged else None,
                            confidence=top["confidence"] if (top and flagged) else None, latency_ms=latency,
                            model_version=models.version, simulated=False, notes=notes)


__all__ = ["InspectionEngine", "ModelNotReadyError"]
