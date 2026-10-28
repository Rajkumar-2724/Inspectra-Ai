"""Lightweight CNN defect classifier adapter (MobileNetV3 / EfficientNet-B0 exports)."""
from dataclasses import dataclass

import numpy as np

from app.ai.patchcore_adapter import IMAGENET_MEAN, IMAGENET_STD, preprocess_for_model

UNKNOWN_DEFECT = "unknown_defect"


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    probabilities: dict[str, float]
    is_unknown: bool


class ClassifierAdapter:
    def __init__(self, runtime, metadata: dict):
        self.runtime, self.meta = runtime, metadata
        self.class_names: list[str] = list(metadata["class_names"])
        self.min_confidence: float = float(metadata.get("min_confidence", 0.6))

    @staticmethod
    def _softmax(z: np.ndarray) -> np.ndarray:
        z = z - z.max()
        e = np.exp(z)
        return e / e.sum()

    def classify(self, crop_rgb: np.ndarray) -> ClassificationResult:
        x = preprocess_for_model(crop_rgb, self.meta["input_size"], self.meta.get("mean", IMAGENET_MEAN),
                                 self.meta.get("std", IMAGENET_STD))
        logits = np.asarray(next(iter(self.runtime.run(x).values())), dtype=np.float32).reshape(-1)
        if logits.size != len(self.class_names):
            raise RuntimeError("Classifier output size does not match class_names")
        probs = logits if (abs(logits.sum() - 1) < 1e-3 and logits.min() >= 0) else self._softmax(logits)
        i = int(np.argmax(probs))
        conf = float(probs[i])
        unknown = conf < self.min_confidence
        return ClassificationResult(UNKNOWN_DEFECT if unknown else self.class_names[i], conf,
                                    {n: float(p) for n, p in zip(self.class_names, probs)}, unknown)
