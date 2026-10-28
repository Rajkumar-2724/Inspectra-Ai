"""Human-readable explanations, defect region formatting, and reference patch comparison."""
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.models.models import Decision


class ExplainabilityService:
    def explain(
        self,
        *,
        score: float,
        review: float,
        fail: float,
        decision: Decision,
        boxes: list[dict],
        simulated: bool,
        mode: str,
        scenario: str | None,
        reference_available: bool,
        localization_status: str = "provisional",
        localization_threshold: float = 0.4,
    ) -> dict[str, Any]:
        if decision == Decision.PASS:
            reason = f"Anomaly score {score:.3f} is below the review threshold {review:.2f}."
        elif decision == Decision.REVIEW:
            reason = f"Anomaly score {score:.3f} is between review ({review:.2f}) and fail ({fail:.2f}); routed to a human reviewer."
        else:
            reason = f"Anomaly score {score:.3f} is at or above the fail threshold {fail:.2f}."

        regions: list[dict[str, Any]] = []
        for idx, b in enumerate(boxes, start=1):
            regions.append({
                "id": b.get("id", idx),
                "shape": b.get("shape", "ellipse"),
                "center": b.get("center", [round(b["x"] + b["w"] / 2.0, 2), round(b["y"] + b["h"] / 2.0, 2)]),
                "axes": b.get("axes", [round(b["w"] / 2.0, 2), round(b["h"] / 2.0, 2)]),
                "angle": b.get("angle", 0.0),
                "box": [b["x"], b["y"], b["w"], b["h"]],
                "original_box": b.get("original_box", [b["x"], b["y"], b["w"], b["h"]]),
                "original_geometry": {
                    "shape": b.get("shape", "ellipse"),
                    "center": b.get("original_center", b.get("center", [b["x"] + b["w"] / 2.0, b["y"] + b["h"] / 2.0])),
                    "axes": b.get("original_axes", b.get("axes", [b["w"] / 2.0, b["h"] / 2.0])),
                    "angle": b.get("angle", 0.0),
                },
                "contour": b.get("contour", []),
                "area": b.get("area", b["w"] * b["h"]),
                "peak_score": round(b.get("peak_score", 0.0), 3),
                "label": b.get("label", "unclassified_anomaly"),
                "defect_name": "Unclassified anomaly" if b.get("label") == "unclassified_anomaly" else b.get("label", "").replace("_", " ").title(),
                "confidence": b.get("confidence"),
                "crop_kind": b.get("crop_kind", f"crop_{b.get('id', idx)}"),
                "crop_data": b.get("crop_data"),
            })

        return {
            "summary": reason,
            "regions": regions,
            "simulated": simulated,
            "mode": mode,
            "scenario": scenario,
            "threshold_status": "PROVISIONAL",
            "threshold_note": "Thresholds are provisional baseline values (0.40 review / 0.70 fail) awaiting ROC calibration against validation set.",
            "localization_status": localization_status,
            "localization_threshold": round(localization_threshold, 4),
            "localization_note": (
                "Pixel-level localization is calibrated."
                if localization_status == "calibrated"
                else "Localization threshold is provisional/uncalibrated. Outlines represent localized anomaly clusters from PatchCore feature distance."
            ),
            "classifier_status": "none_configured",
            "classifier_note": (
                "No trained multi-class defect classifier is configured for this product. "
                "PatchCore detects anomalies by comparing patch embeddings against nominal reference memory; "
                "all localized regions are labeled 'Unclassified anomaly'. Training a dedicated classifier requires labeled defect datasets."
            ),
            "disclaimer": (
                "SIMULATED RESULT: produced by the demonstration engine, not by a trained AI model."
                if simulated
                else "Result produced by a registered, validated model artifact."
            ),
            "reference_patch": {
                "available": reference_available,
                "source": (
                    "Same-region crop from the product's registered reference image. This is a visual aid, "
                    "not a learned nearest-neighbour memory-bank patch."
                    if reference_available
                    else None
                ),
                "unavailable_reason": None
                if reference_available
                else "No reference image registered for this product, or no defect region was located.",
            },
        }

    def reference_patch(self, reference_path: Path | None, size_wh: tuple[int, int], boxes: list[dict]) -> np.ndarray | None:
        if not reference_path or not boxes or not Path(reference_path).is_file():
            return None
        ref = cv2.imread(str(reference_path))
        if ref is None:
            return None
        ref = cv2.cvtColor(cv2.resize(ref, size_wh, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        b = boxes[0]
        pad = 12
        x0, y0 = max(0, b["x"] - pad), max(0, b["y"] - pad)
        x1, y1 = min(size_wh[0], b["x"] + b["w"] + pad), min(size_wh[1], b["y"] + b["h"] + pad)
        patch = ref[y0:y1, x0:x1]
        return patch if patch.size else None
