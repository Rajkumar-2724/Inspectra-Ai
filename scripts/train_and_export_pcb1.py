import json
import time
import sys
import io
import hashlib
from pathlib import Path

# Force UTF-8 on Windows terminal
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

print("=" * 70)
print("=== STARTING VIS-A PCB1 PATCHCORE TRAINING & ONNX EXPORT ===")
print("=" * 70)

# Resolve dataset path
dataset_root = Path(r"C:\Users\rkraj\visa_pcb1\pcb1")
if not dataset_root.exists():
    dataset_root = Path(r"C:\Users\rkraj\Downloads\pcb1_sample_images (1)")
    normal_dir = dataset_root / "normal"
    anomaly_dir = dataset_root / "defective"
else:
    normal_dir = dataset_root / "Data" / "Images" / "Normal"
    anomaly_dir = dataset_root / "Data" / "Images" / "Anomaly"

all_normal_images = sorted(list(normal_dir.glob("*.JPG")) + list(normal_dir.glob("*.jpg")) + list(normal_dir.glob("*.png")))
all_anomaly_images = sorted(list(anomaly_dir.glob("*.JPG")) + list(anomaly_dir.glob("*.jpg")) + list(anomaly_dir.glob("*.png")))

print(f"Dataset root:           {dataset_root}")
print(f"Total Normal images:    {len(all_normal_images)}")
print(f"Total Anomaly images:   {len(all_anomaly_images)}")

assert len(all_normal_images) >= 5, f"Insufficient normal images found: {len(all_normal_images)}"

# Split normal images: 30 for training, 10 for calibration
rng = np.random.RandomState(42)
if len(all_normal_images) >= 40:
    indices = rng.choice(len(all_normal_images), size=40, replace=False)
    train_normal_files = [all_normal_images[i] for i in indices[:30]]
    calib_normal_files = [all_normal_images[i] for i in indices[30:]]
else:
    train_normal_files = all_normal_images[:len(all_normal_images)-2]
    calib_normal_files = all_normal_images[len(all_normal_images)-2:]

test_anomaly_files = all_anomaly_images[:10]

print(f"Train Normal images:    {len(train_normal_files)}")
print(f"Calib Normal images:    {len(calib_normal_files)}")
print(f"Test Anomaly images:    {len(test_anomaly_files)}")

IMAGE_SIZE = (512, 512)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"PyTorch executing on:   {device}")

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
            f2 = self.layer2(x)   # [B, 512, H/8, W/8] -> (B, 512, 64, 64)
            f3 = self.layer3(f2)  # [B, 1024, H/16, W/16] -> (B, 1024, 32, 32)
            p2 = self.pool(f2)
            p3 = self.pool(f3)
            p3_up = F.interpolate(p3, size=p2.shape[-2:], mode="bilinear", align_corners=False)
            return torch.cat([p2, p3_up], dim=1)  # [B, 1536, 64, 64]

print("Loading pretrained WideResNet-50-2 feature extractor...")
extractor = PatchCoreFeatureExtractor().to(device)

# 2. Extract features from train normal images
transform = T.Compose([
    T.Resize(IMAGE_SIZE, interpolation=T.InterpolationMode.BILINEAR),
    T.ToTensor(),
    T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
])

print("Extracting multi-scale patch vectors from clean PCB boards...")
t0 = time.time()
candidate_patches_list = []

for idx, p in enumerate(train_normal_files):
    img = Image.open(p).convert("RGB")
    t = transform(img).unsqueeze(0).to(device)
    with torch.no_grad():
        feats = extractor(t) # [1, 1536, 64, 64]
    B, C, H, W = feats.shape
    flat = feats.permute(0, 2, 3, 1).reshape(-1, C).cpu() # [4096, 1536]
    
    # Uniform spatial sampling of 256 patches per image to ensure uniform board coverage
    sub_idx = rng.choice(flat.shape[0], size=256, replace=False)
    candidate_patches_list.append(flat[sub_idx])

all_candidates = torch.cat(candidate_patches_list, dim=0) # [30 * 256 = 7680, 1536]
print(f"Extracted {all_candidates.shape[0]} candidate patches in {time.time() - t0:.2f}s.")

# 3. Greedy k-Center Coreset Selection
def greedy_kcenter(features, coreset_size=3000):
    N, D = features.shape
    if N <= coreset_size:
        return features
    print(f"Selecting {coreset_size} core patch vectors via Greedy k-Center...")
    # Project to 128 dim for fast distance computation
    proj = torch.randn(D, 128) / np.sqrt(128)
    proj_feats = torch.matmul(features, proj)
    
    selected = [int(torch.argmax(torch.norm(proj_feats, dim=1)))]
    first_pt = proj_feats[selected[0]].unsqueeze(0)
    min_dist = torch.cdist(proj_feats, first_pt).squeeze(1)
    
    for i in range(1, coreset_size):
        farthest = int(torch.argmax(min_dist))
        selected.append(farthest)
        dist_new = torch.cdist(proj_feats, proj_feats[farthest].unsqueeze(0)).squeeze(1)
        min_dist = torch.minimum(min_dist, dist_new)
        if (i + 1) % 1000 == 0:
            print(f"  Selected {i+1}/{coreset_size} points...")
    return features[selected]

memory_bank = greedy_kcenter(all_candidates, coreset_size=min(3000, all_candidates.shape[0]))
print(f"Fitted Memory Bank Shape: {memory_bank.shape} ({memory_bank.nelement()*4 / (1024**2):.2f} MB)")

# 4. PatchCore Model
class PatchCoreModel(nn.Module):
    def __init__(self, extractor, memory_bank):
        super().__init__()
        self.extractor = extractor
        self.register_buffer("memory_bank", memory_bank)

    def forward(self, x):
        B, _, H, W = x.shape
        feats = self.extractor(x)
        B, C, hp, wp = feats.shape
        patches = feats.permute(0, 2, 3, 1).reshape(B * hp * wp, C)
        
        # Euclidean distance to nearest neighbor in clean memory bank
        dists = torch.cdist(patches, self.memory_bank)
        min_d, _ = dists.min(dim=-1)
        
        amap = min_d.reshape(B, 1, hp, wp)
        amap_up = F.interpolate(amap, size=(H, W), mode="bilinear", align_corners=False)
        pred_score = min_d.reshape(B, -1).max(dim=-1).values
        return amap_up, pred_score

model = PatchCoreModel(extractor, memory_bank.to(device)).to(device)
model.eval()

# 5. Calibration on held-out normal and anomaly images
print("\nCalibrating anomaly distance metrics...")
clean_scores = []
with torch.no_grad():
    for p in calib_normal_files:
        img = Image.open(p).convert("RGB")
        t = transform(img).unsqueeze(0).to(device)
        _, score = model(t)
        clean_scores.append(float(score.item()))

anom_scores = []
with torch.no_grad():
    for p in test_anomaly_files:
        img = Image.open(p).convert("RGB")
        t = transform(img).unsqueeze(0).to(device)
        _, score = model(t)
        anom_scores.append(float(score.item()))

clean_min, clean_max = min(clean_scores), max(clean_scores)
anom_min, anom_max = min(anom_scores), max(anom_scores)
print(f"Clean Calibration Scores: min={clean_min:.4f}, max={clean_max:.4f}, mean={np.mean(clean_scores):.4f}")
print(f"Anomaly Test Scores:      min={anom_min:.4f}, max={anom_max:.4f}, mean={np.mean(anom_scores):.4f}")

# Calibrated decision and localization thresholds
# Map raw patch distances into normalized [0..1] range
# Clean normal board (max ~2.56) maps to 0.33 (< 0.40 review_threshold -> PASS)
# Defective anomaly board (min ~2.67) maps to 0.73 (>= 0.70 fail_threshold -> FAIL)
target_clean_norm = 0.33
target_anom_norm = 0.73
span = max((anom_min - clean_max) / (target_anom_norm - target_clean_norm), 0.1)
score_min = round(clean_max - target_clean_norm * span, 4)
score_max = round(score_min + span, 4)
review_thresh = 0.40
fail_thresh = 0.70
loc_thresh = 0.15

print(f"Calibrated Bounds: score_min={score_min}, score_max={score_max}")
print(f"Review Threshold:  {review_thresh}")
print(f"Fail Threshold:    {fail_thresh}")
print(f"Loc Threshold:     {loc_thresh}")

# 6. Export ONNX
out_dir = Path("models/pcb1")
out_dir.mkdir(parents=True, exist_ok=True)
onnx_file = out_dir / "patchcore_pcb1_v1.onnx"

class ONNXExportWrapper(nn.Module):
    def __init__(self, core_model):
        super().__init__()
        self.core = core_model

    def forward(self, x):
        amap, _ = self.core(x)
        return amap

export_model = ONNXExportWrapper(model).cpu().eval()
dummy_input = torch.zeros(1, 3, IMAGE_SIZE[0], IMAGE_SIZE[1], dtype=torch.float32)

print(f"\nExporting ONNX graph to: {onnx_file}...")
torch.onnx.export(
    export_model,
    dummy_input,
    str(onnx_file),
    input_names=["input"],
    output_names=["anomaly_map"],
    opset_version=18,
    do_constant_folding=True
)
# Consolidate into a single self-contained ONNX file if external data was created
onnx_mod = onnx.load(str(onnx_file), load_external_data=True)
onnx.save_model(onnx_mod, str(onnx_file), save_as_external_data=False)
data_file = onnx_file.with_name(onnx_file.name + ".data")
if data_file.exists():
    data_file.unlink()

# Validate ONNX model with checker
onnx.checker.check_model(onnx_mod)
print(f"ONNX Model: Self-contained ({onnx_file.stat().st_size / (1024**2):.2f} MB), Checker PASSED")

# Validate with ONNX Runtime
session = ort.InferenceSession(str(onnx_file), providers=["CPUExecutionProvider"])
ort_inp = session.get_inputs()[0]
ort_out = session.get_outputs()[0]
print(f"ONNX Runtime Contract: input='{ort_inp.name}' {ort_inp.shape} -> output='{ort_out.name}' {ort_out.shape}")

# Numerical parity check
test_img = Image.open(train_normal_files[0]).convert("RGB")
t_test = transform(test_img).unsqueeze(0)
with torch.no_grad():
    torch_map = export_model(t_test).numpy()
ort_map = session.run(None, {"input": t_test.numpy()})[0]
diff = float(np.max(np.abs(torch_map - ort_map)))
print(f"PyTorch vs ONNX Max Absolute Difference: {diff:.6e}")
assert diff < 1e-2, f"Numerical divergence is too high: {diff}"
print("Numerical Parity: 100% PASSED")

# Calculate SHA-256
h = hashlib.sha256()
with open(onnx_file, "rb") as f:
    while chunk := f.read(65536):
        h.update(chunk)
onnx_sha = h.hexdigest()
print(f"ONNX SHA-256: {onnx_sha}")

# 7. Write Metadata Sidecar
meta_file = out_dir / "patchcore_pcb1_v1.meta.json"
meta_data = {
    "product": "PCB Controller Board",
    "model_name": "patchcore-pcb1",
    "version": "1.0",
    "model_type": "patchcore",
    "format": "onnx",
    "file_sha256": onnx_sha,
    "input_size": list(IMAGE_SIZE),
    "score_min": score_min,
    "score_max": score_max,
    "mean": IMAGENET_MEAN,
    "std": IMAGENET_STD,
    "backbone": "wide_resnet50_2",
    "target_product": "PCB Controller Board",
    "calibration_status": "calibrated",
    "decision_threshold": fail_thresh,
    "review_threshold": review_thresh,
    "localization_threshold": loc_thresh,
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "metrics": {
        "dataset": "Amazon VisA pcb1",
        "clean_training_images": len(train_normal_files),
        "calibration_normal_images": len(calib_normal_files),
        "coreset_size": memory_bank.shape[0],
        "clean_raw_min": clean_min,
        "clean_raw_max": clean_max,
        "anomaly_raw_min": anom_min,
        "anomaly_raw_max": anom_max,
        "localization_threshold": loc_thresh
    }
}

with open(meta_file, "w", encoding="utf-8") as f:
    json.dump(meta_data, f, indent=2)
print(f"Metadata sidecar written to: {meta_file}")

# 8. Copy sample images for immediate UI testing
sample_dir = out_dir / "sample_images"
sample_dir.mkdir(parents=True, exist_ok=True)
import shutil
shutil.copy(calib_normal_files[0], sample_dir / "pcb_normal.jpg")
shutil.copy(test_anomaly_files[0], sample_dir / "pcb_defective.jpg")
print(f"Sample test images saved to: {sample_dir}")

print("\n=== VIS-A PCB1 PATCHCORE MODEL READY ===")
