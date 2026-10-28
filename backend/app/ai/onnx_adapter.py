"""Inference runtimes. ONNX Runtime is the primary (safe, no pickle) path.

TorchScript is supported as an optional alternative. Arbitrary pickled PyTorch objects
(.pth/.pt via torch.load, .ckpt) are NEVER loaded: export to ONNX or TorchScript instead.
"""
from pathlib import Path

import numpy as np


class RuntimeLoadError(RuntimeError):
    pass


class ONNXRuntimeAdapter:
    runtime_name = "onnxruntime"

    def __init__(self, path: Path, providers: list[str] | None = None):
        try:
            import onnxruntime as ort
        except ImportError as e:  # pragma: no cover
            raise RuntimeLoadError("onnxruntime is not installed") from e
        try:
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            self.session = ort.InferenceSession(str(path), sess_options=opts, providers=providers or ["CPUExecutionProvider"])
        except Exception as e:
            raise RuntimeLoadError(f"Invalid or unsupported ONNX file: {e}") from e
        inp = self.session.get_inputs()[0]
        self.input_name, self.input_shape = inp.name, list(inp.shape)
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.output_shapes = [list(o.shape) for o in self.session.get_outputs()]
        self.version = ort.__version__

    @property
    def runtime(self) -> str:
        return f"onnxruntime {self.version}"

    def run(self, x: np.ndarray) -> dict[str, np.ndarray]:
        outs = self.session.run(None, {self.input_name: x.astype(np.float32)})
        return dict(zip(self.output_names, outs))


class TorchScriptAdapter:
    runtime_name = "torchscript"

    def __init__(self, path: Path):
        try:
            import torch
        except ImportError as e:
            raise RuntimeLoadError("PyTorch is not installed (pip install -r requirements-ai.txt)") from e
        self._torch = torch
        try:
            self.module = torch.jit.load(str(path), map_location="cpu").eval()
        except Exception as e:
            raise RuntimeLoadError(f"Invalid TorchScript file: {e}") from e
        self.input_shape: list = []
        self.output_names: list[str] = []
        self.output_shapes: list = []

    @property
    def runtime(self) -> str:
        return f"torchscript torch {self._torch.__version__}"

    def run(self, x: np.ndarray) -> dict[str, np.ndarray]:
        with self._torch.no_grad():
            out = self.module(self._torch.from_numpy(x.astype(np.float32)))
        if isinstance(out, dict):
            return {k: v.cpu().numpy() for k, v in out.items()}
        if isinstance(out, (tuple, list)):
            return {f"output_{i}": v.cpu().numpy() for i, v in enumerate(out)}
        return {"output_0": out.cpu().numpy()}


def load_runtime(path: Path, fmt: str):
    if fmt == "onnx":
        return ONNXRuntimeAdapter(path)
    if fmt == "torchscript":
        return TorchScriptAdapter(path)
    raise RuntimeLoadError(f"Unsupported model format '{fmt}' (allowed: onnx, torchscript)")
