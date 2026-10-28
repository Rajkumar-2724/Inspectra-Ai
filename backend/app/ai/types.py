from dataclasses import dataclass, field

import numpy as np

from app.models.models import Decision


@dataclass
class EngineResult:
    mode: str  # "demo" | "real"
    score: float
    raw_score: float | None
    decision: Decision
    heatmap: np.ndarray  # float32 HxW 0..1 at processed-image resolution
    boxes: list[dict]  # {x,y,w,h,area,peak_score,label,confidence}
    defect_class: str | None
    confidence: float | None
    latency_ms: float
    model_version: str
    simulated: bool
    scenario: str | None = None
    notes: list[str] = field(default_factory=list)
