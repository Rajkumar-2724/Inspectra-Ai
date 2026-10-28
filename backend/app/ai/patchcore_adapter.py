"""PatchCore anomaly-detection adapter (runtime-agnostic).

Expected exported artifact contract (see docs/AI_MODEL_INTEGRATION.md):
  input : float32 NCHW, RGB, scaled 0..1 then (x-mean)/std
  output: an anomaly map (N,1,H,W | N,H,W | H,W) and optionally a scalar image score.
Metadata sidecar JSON provides: input_size [H,W], score_min, score_max, mean, std.
Raw scores are min-max normalised to 0..1 using the calibration values in the sidecar.
"""
from dataclasses import dataclass

import cv2
import numpy as np

IMAGENET_MEAN, IMAGENET_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]


@dataclass
class PatchCoreOutput:
    score: float  # normalised 0..1
    raw_score: float
    heatmap: np.ndarray  # float32 HxW normalised 0..1 (model resolution)


def preprocess_for_model(rgb: np.ndarray, input_size: list[int], mean: list[float], std: list[float]) -> np.ndarray:
    h, w = int(input_size[0]), int(input_size[1])
    x = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    x = (x - np.array(mean, dtype=np.float32)) / np.array(std, dtype=np.float32)
    return np.transpose(x, (2, 0, 1))[None]


class PatchCoreAdapter:
    def __init__(self, runtime, metadata: dict):
        self.runtime, self.meta = runtime, metadata

    def predict(self, rgb: np.ndarray) -> PatchCoreOutput:
        m = self.meta
        x = preprocess_for_model(rgb, m["input_size"], m.get("mean", IMAGENET_MEAN), m.get("std", IMAGENET_STD))
        outs = list(self.runtime.run(x).values())
        amap, scalar = None, None
        for o in outs:
            o = np.asarray(o, dtype=np.float32)
            if o.ndim >= 2 and o.size > 1 and amap is None:
                amap = np.squeeze(o)
            elif o.size == 1 and scalar is None:
                scalar = float(o.reshape(-1)[0])
        if amap is None or amap.ndim != 2:
            raise RuntimeError("PatchCore model produced no 2-D anomaly map")
        lo, hi = float(m["score_min"]), float(m["score_max"])
        span = max(hi - lo, 1e-9)
        raw = scalar if scalar is not None else float(amap.max())
        return PatchCoreOutput(score=float(np.clip((raw - lo) / span, 0, 1)), raw_score=raw,
                               heatmap=np.clip((amap - lo) / span, 0, 1).astype(np.float32))
