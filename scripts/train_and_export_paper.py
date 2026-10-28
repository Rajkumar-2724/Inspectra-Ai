import json
import time
import sys
import io
from pathlib import Path

# Force UTF-8 on Windows terminal to prevent UnicodeEncodeError on emoji print
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from PIL import Image
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T
from torchvision.models import wide_resnet50_2, Wide_ResNet50_2_Weights
import onnx
import onnxruntime as ort

print("=== STARTING PAPER PATCHCORE TRAINING & EXPORT ===")

dataset_root = Path(r"C:\Users\rkraj\paper_dataset")
train_good_dir = dataset_root / "train" / "good"
test_dot_dir = dataset_root / "test" / "dot"

train_images = sorted(list(train_good_dir.glob("*.jpg")) + list(train_good_dir.glob("*.png")))
test_images = sorted(list(test_dot_dir.glob("*.jpg")) + list(test_dot_dir.glob("*.png")))

print(f"Dataset location: {dataset_root}")
print(f"Clean training images: {[p.name for p in train_images]} (Count: {len(train_images)})")
print(f"Test dotted images:   {[p.name for p in test_images]} (Count: {len(test_images)})")

assert len(train_images) == 2, f"Expected 2 train images, found {len(train_images)}"
assert len(test_images) == 2, f"Expected 2 test images, found {len(test_images)}"

IMAGE_SIZE = (512, 512)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"PyTorch executing on: {device}")

# 1. Feature Extractor
class PatchCoreFeatureExtractor(nn.Module):
    def __init__(self):
        super().__init__()
        weights = Wide_ResNet50_2_Weights.IMAGENET1K_V1
        backbone = wide_resnet50_2(weights=weights)
        self.conv1 = backbone.conv1
        self.bn1 = backbone.bn1
        self.relu = backbone.relu
        self.maxpool = backbone.maxpool
        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        for p in self.parameters():
            p.requires_grad = False
        self.eval()
        self.pool = nn.AvgPool2d(kernel_size=3, stride=1, padding=1)

    def forward(self, x):
        with torch.no_grad():
            x = self.conv1(x)
            x = self.bn1(x)
            x = self.relu(x)
            x = self.maxpool(x)
            x = self.layer1(x)
            f2 = self.layer2(x)   # [B, 512, H/8, W/8]
            f3 = self.layer3(f2)  # [B, 1024, H/16, W/16]
            p2 = self.pool(f2)
            p3 = self.pool(f3)
            p3_up = F.interpolate(p3, size=p2.shape[-2:], mode="bilinear", align_corners=False)
            return torch.cat([p2, p3_up], dim=1)  # [B, 1536, 64, 64]

print("Loading pretrained WideResNet-50-2 feature extractor...")
extractor = PatchCoreFeatureExtractor().to(device)

# 2. Extract features from clean images ONLY
transform = T.Compose([
    T.Resize(IMAGE_SIZE, interpolation=T.InterpolationMode.BILINEAR),
    T.ToTensor(),
    T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
])

clean_tensors = []
for p in train_images:
    img = Image.open(p).convert("RGB")
    t = transform(img).unsqueeze(0).to(device)
    clean_tensors.append(t)

clean_batch = torch.cat(clean_tensors, dim=0) # [2, 3, 512, 512]
with torch.no_grad():
    feats = extractor(clean_batch) # [2, 1536, 64, 64]

B, C, H, W = feats.shape
patches = feats.permute(0, 2, 3, 1).reshape(-1, C).cpu() # [8192, 1536]
print(f"Extracted normal patch embeddings: shape={patches.shape} ({patches.nelement()*4 / (1024*1024):.2f} MB)")

# 3. PatchCore Inference Model
class PatchCoreModel(nn.Module):
    def __init__(self, extractor, memory_bank):
        super().__init__()
        self.extractor = extractor
        self.register_buffer("memory_bank", memory_bank)

    def forward(self, x):
        B, _, H, W = x.shape
        feats = self.extractor(x)  # [B, C, hp, wp]
        B, C, hp, wp = feats.shape
        p = feats.permute(0, 2, 3, 1).reshape(-1, C)
        
        # Euclidean distance to nearest neighbor
        dists = torch.cdist(p, self.memory_bank)
        min_d, _ = dists.min(dim=-1)
        
        amap = min_d.reshape(B, 1, hp, wp)
        amap_up = F.interpolate(amap, size=(H, W), mode="bilinear", align_corners=False)
        pred_score = min_d.reshape(B, -1).max(dim=-1).values
        return amap_up, pred_score

model = PatchCoreModel(extractor, patches.to(device)).to(device)
model.eval()

# 4. Measure Raw Anomaly Scores on all 4 images
print("\n=== MEASURING REAL INFERENCE ANOMALY SCORES ===")
results = {}

all_samples = [("clean", p) for p in train_images] + [("dot", p) for p in test_images]
for category, p in all_samples:
    img = Image.open(p).convert("RGB")
    t = transform(img).unsqueeze(0).to(device)
    with torch.no_grad():
        amap, sc = model(t)
    raw_score = float(sc.cpu().item())
    amap_np = amap.squeeze().cpu().numpy()
    results[p.name] = {
        "category": category,
        "raw_score": round(raw_score, 4),
        "min_dist": round(float(amap_np.min()), 4),
        "max_dist": round(float(amap_np.max()), 4),
        "mean_dist": round(float(amap_np.mean()), 4)
    }
    print(f"  {category.upper():6s} | {p.name:40s} | Raw Score: {raw_score:.4f} | Dist Range: [{amap_np.min():.4f} .. {amap_np.max():.4f}]")

clean_scores = [v["raw_score"] for v in results.values() if v["category"] == "clean"]
dot_scores = [v["raw_score"] for v in results.values() if v["category"] == "dot"]
print(f"\nSummary:")
print(f"  Clean Training Scores: min={min(clean_scores):.4f}, max={max(clean_scores):.4f}")
print(f"  Dotted Test Scores:    min={min(dot_scores):.4f}, max={max(dot_scores):.4f}")

# 5. Export ONNX Model to models/paper/
output_dir = Path("models/paper")
output_dir.mkdir(parents=True, exist_ok=True)
onnx_path = output_dir / "paper_patchcore_v1.onnx"
meta_path = output_dir / "paper_patchcore_v1.meta.json"

class ONNXExportWrapper(nn.Module):
    def __init__(self, core_model):
        super().__init__()
        self.core = core_model
    def forward(self, x):
        amap, _ = self.core(x)
        return amap

export_model = ONNXExportWrapper(model).cpu().eval()
dummy_x = torch.zeros(1, 3, IMAGE_SIZE[0], IMAGE_SIZE[1], dtype=torch.float32)

print(f"\nExporting ONNX graph to {onnx_path}...")
torch.onnx.export(
    export_model,
    dummy_x,
    str(onnx_path),
    input_names=["input"],
    output_names=["anomaly_map"],
    opset_version=14,
    do_constant_folding=True
)
# Embed external data into a single self-contained ONNX model if needed
onnx_m = onnx.load(str(onnx_path), load_external_data=True)
onnx.save(onnx_m, str(onnx_path), save_as_external_data=False)
data_file = Path(str(onnx_path) + ".data")
if data_file.exists():
    data_file.unlink()

print(f"Self-contained ONNX Model saved: {onnx_path} ({onnx_path.stat().st_size / (1024*1024):.2f} MB)")

# 6. Verify ONNX Graph and ONNX Runtime
onnx.checker.check_model(onnx_m)
print("ONNX Graph Structure Validation: PASSED")

ort_sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
ort_in = ort_sess.get_inputs()
ort_out = ort_sess.get_outputs()
print(f"ONNX Runtime Contract:")
print(f"  Input:  {ort_in[0].name} {ort_in[0].shape} {ort_in[0].type}")
print(f"  Output: {ort_out[0].name} {ort_out[0].shape} {ort_out[0].type}")

# Numerical parity check
test_t = clean_tensors[0].cpu()
with torch.no_grad():
    pyt_amap = export_model(test_t).numpy()
ort_amap = ort_sess.run(None, {"input": test_t.numpy()})[0]
diff = np.max(np.abs(pyt_amap - ort_amap))
print(f"Parity Check (PyTorch vs ONNX Runtime): max diff = {diff:.6e}")
assert diff < 1e-2, f"Difference too high: {diff}"
print("Parity Check: PASSED!")

# 7. Write models/paper/paper_patchcore_v1.meta.json
score_min = float(round(min(clean_scores) * 0.95, 4))
score_max = float(round(max(dot_scores) * 1.05, 4))
if score_max <= score_min:
    score_max = score_min + 1.0

meta_payload = {
    "input_size": list(IMAGE_SIZE),
    "score_min": score_min,
    "score_max": score_max,
    "mean": IMAGENET_MEAN,
    "std": IMAGENET_STD,
    "backbone": "wide_resnet50_2",
    "target_product": "Plain Paper",
    "calibration_status": "uncalibrated",
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "metrics": {
        "dataset": "Paper Anomaly Feasibility Dataset",
        "clean_training_images": len(train_images),
        "test_images": len(test_images),
        "defect_categories": ["dot"],
        "calibration_status": "uncalibrated",
        "decision_threshold": None,
        "localization_threshold": None
    },
    "measured_scores": results
}

meta_path.write_text(json.dumps(meta_payload, indent=2))
print(f"Metadata written: {meta_path}")
print("=== TRAINING AND EXPORT COMPLETED SUCCESSFULLY ===")
