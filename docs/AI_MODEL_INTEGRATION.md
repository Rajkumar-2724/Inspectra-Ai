# AI model integration (no training included)

This project contains **no trained weights** and ran **no training**. Real AI mode stays disabled until you supply
artifacts that pass validation. Demo mode is separate, explicitly selected, and always labelled *simulated*.

## Pipeline

`upload → validate → EXIF orientation → aspect-preserving resize → PatchCoreAdapter (score + anomaly map)
→ HeatmapProcessor (normalise/smooth/colourise) → DefectLocalizer (connected components ≥ review threshold)
→ ClassifierAdapter per region (low confidence ⇒ "unknown_defect") → DecisionEngine (PASS/REVIEW/FAIL)
→ ExplainabilityService → storage + hash-chained audit event`

Real mode never falls back to demo output: if the product's model is not READY the API answers `409 REAL_MODE_UNAVAILABLE`.

## Artifact contract

Put `name.onnx` and `name.meta.json` inside `models/` (path traversal outside is rejected).

**PatchCore (anomaly) — ONNX**
- Input: `float32 [1,3,H,W]`, RGB, `x/255`, then `(x-mean)/std` (ImageNet mean/std unless overridden).
- Output: an anomaly map (`[1,1,H,W]`, `[1,H,W]` or `[H,W]`) and optionally a scalar image score. If no scalar is present the map maximum is used.
- Sidecar:
```json
{ "input_size": [256, 256], "score_min": 0.0, "score_max": 25.0,
  "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225] }
```
`score_min/score_max` are **calibration values you measure on good/defective validation images**; the adapter min-max normalises raw scores to 0–1 so the 0–1 thresholds mean something. Poor calibration means poor decisions — calibrate on real data.

**Classifier (MobileNetV3 / EfficientNet-B0) — ONNX**
- Input: `float32 [1,3,H,W]` crop of the flagged region. Output: logits or probabilities, length = number of classes.
- Sidecar:
```json
{ "input_size": [224, 224], "class_names": ["scratch", "crack", "dent"], "min_confidence": 0.6 }
```
Confidence below `min_confidence` ⇒ label `unknown_defect`.

## Validation performed on register / re-validate / file change
1. Path inside `models/`; extension matches declared format; pickle formats refused.
2. File exists (else `FILE_MISSING`); sidecar exists and has required keys (else `INVALID`).
3. Runtime loads the file (ONNX Runtime; TorchScript needs `requirements-ai.txt`).
4. Static input dims agree with `input_size`; a zero-tensor forward pass produces a 2-D map (PatchCore) or `len(class_names)` outputs (classifier).
5. Result stored as `READY`, `INVALID`, `FILE_MISSING` or `ERROR` with a reason. Files are re-checked (mtime/size) at inference time.

A model is usable only for the **product it is registered to** (compatibility check on every inference).

## Registering
- UI: *Models → Register model*, or
- File: copy `models/registry.example.yaml` → `models/registry.yaml`, then from `backend/`: `python -m app.scripts.register_models`.
Then assign the models to the product (*Products → Edit*) if not done at registration.

## Exporting (examples, **not executed or verified in this repository**)
Training/exports happen outside this app, e.g. with Anomalib (`pip install -r backend/requirements-ai.txt`):
```python
from anomalib.engine import Engine
engine.export(model=model, export_type="onnx", export_root="exports/")   # check the anomalib docs for your version
```
Anomalib's exported graph and output names vary by version; verify it satisfies the contract above (2-D map output, calibrated
`score_min/score_max`) and adjust the sidecar. For a torchvision classifier use `torch.onnx.export(model, torch.zeros(1,3,224,224), "clf.onnx", opset_version=17)`.

## Latency
`latency_ms` measures PatchCore + classifier inference only (preprocessing excluded), per inspection. Benchmark on your
hardware before making real-time claims. Demo-mode latency is meaningless for deployment sizing.

## Evaluation
The UI never shows accuracy/precision/recall/F1/AUROC. Attach verified labels (`POST /api/analytics/ground-truth`, or the
*Mark good/defective* buttons on an inspection) to obtain false-pass/false-fail counts. Extend `analytics.py::_evaluation`
once you have a proper held-out labelled set.
