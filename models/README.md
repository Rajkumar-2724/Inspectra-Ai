# models/

Place **trained model artifacts** here. This repository ships **no weights** and no model was trained for it.

```
models/
  pcb/
    patchcore_pcb_v1.onnx
    patchcore_pcb_v1.meta.json      # required sidecar
    classifier_pcb_v1.onnx
    classifier_pcb_v1.meta.json
  registry.yaml                     # optional (see registry.example.yaml)
```

Accepted: `.onnx` (recommended) and TorchScript (`.pt`, `.ts`, `.torchscript`).
Refused: pickle checkpoints (`.pth`, `.ckpt`, `.pkl`) because they can execute arbitrary code when loaded.

Full contract and export examples: `docs/AI_MODEL_INTEGRATION.md`.
Weights are excluded from git and from the project ZIP (`.gitignore`).
