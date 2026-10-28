"""Deterministic DEMONSTRATION engine. Every output is SIMULATED, never a real AI prediction.

The scenario (or a hash of the image when scenario == "auto") fully determines the simulated
anomaly score and heatmap. The heatmap is then run through the same HeatmapProcessor /
DefectLocalizer / DecisionEngine used for real inference so the full UI pipeline is exercised.
"""
import hashlib
import math
import time

import numpy as np

from app.ai.decision_engine import DecisionEngine
from app.ai.localization import DefectLocalizer, HeatmapProcessor
from app.ai.types import EngineResult
from app.models.models import Decision

DEMO_VERSION = "demo-simulator:1.0"
SCENARIOS: dict[str, dict] = {
    "good": {"title": "Good product", "expected": "PASS", "description": "Clean part; simulated low anomaly score."},
    "obvious_defect": {"title": "Obvious defect", "expected": "FAIL", "description": "Clear scratch/crack; simulated high score."},
    "subtle_defect": {"title": "Subtle defect", "expected": "REVIEW", "description": "Faint blemish; score between thresholds."},
    "unknown_defect": {"title": "Unknown defect", "expected": "REVIEW", "description": "Irregular anomaly the classifier cannot name."},
    "lighting_variation": {"title": "Lighting / rotation variation", "expected": "PASS", "description": "Good part under altered lighting or rotation; preprocessing keeps it a PASS."},
}
AUTO = "auto"
FALLBACK_CLASSES = ["scratch", "crack", "dent"]


def _seed(image_sha: str, scenario: str) -> int:
    return int(hashlib.sha256(f"{image_sha}:{scenario}".encode()).hexdigest()[:8], 16)


def _blob(h: int, w: int, cx: int, cy: int, sx: float, sy: float, theta: float, amp: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xx - cx, yy - cy
    c, s = math.cos(theta), math.sin(theta)
    u, v = dx * c + dy * s, -dx * s + dy * c
    return (amp * np.exp(-0.5 * ((u / sx) ** 2 + (v / sy) ** 2))).astype(np.float32)


class DemoInspectionEngine:
    def __init__(self):
        self.heat, self.localizer = HeatmapProcessor(), DefectLocalizer()

    @staticmethod
    def resolve_scenario(scenario: str | None, image_sha: str) -> str:
        if scenario and scenario != AUTO:
            if scenario not in SCENARIOS:
                raise ValueError(f"Unknown demo scenario '{scenario}'")
            return scenario
        keys = list(SCENARIOS)
        return keys[int(image_sha[:8], 16) % len(keys)]

    def run(self, rgb: np.ndarray, image_sha: str, scenario: str | None, review: float, fail: float,
            defect_classes: list[str]) -> EngineResult:
        t0 = time.perf_counter()
        sc = self.resolve_scenario(scenario, image_sha)
        rng = np.random.default_rng(_seed(image_sha, sc))
        u = float(rng.random())
        h, w = rgb.shape[:2]
        m = max(h, w)
        classes = defect_classes or FALLBACK_CLASSES

        if sc == "good":
            score = review * (0.25 + 0.35 * u)
        elif sc == "lighting_variation":
            score = review * (0.45 + 0.30 * u)
        elif sc == "subtle_defect":
            score = review + (fail - review) * (0.30 + 0.30 * u)
        elif sc == "unknown_defect":
            score = review + (fail - review) * (0.55 + 0.20 * u)
        else:
            score = fail + (1 - fail) * (0.40 + 0.50 * u)
        score = float(min(1.0, round(score, 4)))

        cx, cy = int(w * (0.3 + 0.4 * rng.random())), int(h * (0.3 + 0.4 * rng.random()))
        theta = float(rng.random() * math.pi)
        hm = np.zeros((h, w), dtype=np.float32)
        if sc in ("good", "lighting_variation"):
            hm = _blob(h, w, cx, cy, 0.18 * m, 0.14 * m, theta, score)
        elif sc == "obvious_defect":
            hm = _blob(h, w, cx, cy, 0.14 * m, 0.025 * m, theta, score)  # elongated, scratch-like
        elif sc == "subtle_defect":
            hm = _blob(h, w, cx, cy, 0.045 * m, 0.04 * m, theta, score)
        else:
            hm = np.maximum(_blob(h, w, cx, cy, 0.07 * m, 0.03 * m, theta, score),
                            _blob(h, w, min(w - 1, cx + int(0.12 * m)), min(h - 1, cy + int(0.07 * m)), 0.03 * m, 0.05 * m, theta + 1.0, score * 0.93))
        bg = self.heat.smooth(rng.random((h, w)).astype(np.float32), 6.0)
        hm = np.maximum(hm, (bg - bg.min()) / max(float(np.ptp(bg)), 1e-6) * 0.15 * review)  # low-level noise floor
        hm = self.heat.normalize(hm)

        decision = DecisionEngine.decide(score, review, fail)
        regions = self.localizer.locate(hm, review)
        if decision != Decision.PASS and not regions:  # guarantee visible evidence for flagged demos
            s = max(6, int(0.04 * m))
            regions = [type("R", (), dict(x=max(0, cx - s), y=max(0, cy - s), w=2 * s, h=2 * s, area=4 * s * s, peak=score))()]
        if decision == Decision.PASS:
            regions = []

        label, conf = None, None
        if sc == "unknown_defect":
            label, conf = "unknown_defect", round(0.28 + 0.12 * float(rng.random()), 3)
        elif sc == "subtle_defect":
            label, conf = classes[int(rng.integers(len(classes)))], round(0.62 + 0.12 * float(rng.random()), 3)
        elif sc == "obvious_defect":
            label, conf = classes[int(rng.integers(len(classes)))], round(0.88 + 0.08 * float(rng.random()), 3)
        boxes = [{"x": r.x, "y": r.y, "w": r.w, "h": r.h, "area": r.area, "peak_score": float(r.peak),
                  "label": label or "unknown_defect", "confidence": conf} for r in regions]
        return EngineResult(
            mode="demo", score=score, raw_score=None, decision=decision, heatmap=hm, boxes=boxes,
            defect_class=label if decision != Decision.PASS else None,
            confidence=conf if decision != Decision.PASS else None,
            latency_ms=(time.perf_counter() - t0) * 1000, model_version=DEMO_VERSION, simulated=True, scenario=sc,
            notes=["SIMULATED: deterministic demonstration output, not a trained-model prediction."])
