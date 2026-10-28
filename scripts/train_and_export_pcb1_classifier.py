"""Train and Export MobileNetV3 Defect Classifier for VisA PCB1.

Stage 2: Crops localized defect regions and classifies into genuine VisA defect categories:
  - bent
  - melt
  - missing
  - scratch

Includes:
  - Multiclass mask contour extraction with contextual padding
  - Strict leakage-free image-level split (Train: 60, Val: 20, Test: 20)
  - Class-weighted CrossEntropyLoss to address class imbalance
  - Training-only data augmentations
  - Transfer learning on MobileNetV3-Small (ImageNet pretrained)
  - Validation-selected checkpoint based on Macro F1
  - Evaluation on unseen Test set (Precision, Recall, F1, Confusion Matrix)
  - ONNX export with opset 18 and numerical parity check
  - Metadata sidecar generation with class mapping and abstention threshold
"""
import io
import json
import time
import sys
import os
import hashlib
from pathlib import Path
from collections import Counter

# Terminal UTF-8 handling on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

from PIL import Image
import numpy as np
import scipy.ndimage as ndi
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T
import torchvision.models as models
from torchvision.models import MobileNet_V3_Small_Weights
import onnx
import onnxruntime as ort

out_dir = Path("models/pcb1")
out_dir.mkdir(parents=True, exist_ok=True)

print("=" * 70, flush=True)
print("=== STARTING VIS-A PCB1 MOBILENET-V3 DEFECT CLASSIFIER TRAINING ===", flush=True)
print("=" * 70, flush=True)

# 1. Dataset Resolution & Multiclass Label Verification
dataset_root = Path(r"C:\Users\rkraj\visa_pcb1\pcb1")
if not dataset_root.exists():
    dataset_root = Path(r"C:\Users\rkraj\Downloads\pcb1_sample_images (1)")
    img_dir = dataset_root / "defective"
    mask_dir = dataset_root / "masks"
else:
    img_dir = dataset_root / "Data" / "Images" / "Anomaly"
    mask_dir = dataset_root / "Data" / "Masks" / "Anomaly"

CLASS_MAP = {
    1: "bent",
    2: "melt",
    3: "scratch",
    4: "missing"
}
CLASS_NAMES = ["bent", "melt", "missing", "scratch"]  # Lexicographical index mapping 0..3
CLASS_TO_IDX = {name: i for i, name in enumerate(CLASS_NAMES)}

print(f"Dataset root:           {dataset_root}")
print(f"Defect classes (4):     {CLASS_NAMES}")

# 2. Extract Labelled Crops from Verified Masks
print("\nScanning anomaly masks and extracting contextual defect crops...")
all_crop_records = []
all_img_files = sorted(list(img_dir.glob("*.JPG")) + list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")))
# Deduplicate (Windows filesystem case insensitivity)
seen_stems = set()
dedup_img_files = []
for p in all_img_files:
    if p.stem not in seen_stems:
        seen_stems.add(p.stem)
        dedup_img_files.append(p)

all_img_files = dedup_img_files
print(f"Total anomaly board images: {len(all_img_files)}")

# 3. Create a Documented Leakage-Free Image-Level Split
# 60 Train images, 20 Val images, 20 Test images
rng = np.random.RandomState(42)

# Determine primary defect category per image for stratified splitting
img_primary_label = {}
for img_path in all_img_files:
    mask_path = mask_dir / (img_path.stem + ".png")
    if not mask_path.exists():
        continue
    mask_arr = np.array(Image.open(mask_path))
    present_vals = [v for v in np.unique(mask_arr) if v in CLASS_MAP]
    if not present_vals:
        continue
    # Most prevalent class in mask
    counts = {v: np.count_nonzero(mask_arr == v) for v in present_vals}
    primary_val = max(counts, key=counts.get)
    img_primary_label[img_path.stem] = CLASS_MAP[primary_val]

# Group image stems by primary class
class_to_stems = {c: [] for c in CLASS_NAMES}
for stem, c in img_primary_label.items():
    class_to_stems[c].append(stem)

train_stems, val_stems, test_stems = set(), set(), set()
for c in CLASS_NAMES:
    stems = sorted(class_to_stems[c])
    rng.shuffle(stems)
    n = len(stems)
    n_test = max(1, int(round(n * 0.20)))
    n_val = max(1, int(round(n * 0.20)))
    n_train = n - n_test - n_val
    # Adjust for small counts
    if n_train < 1:
        n_train = 1
        if n_val > 1: n_val -= 1
        elif n_test > 1: n_test -= 1

    c_train = stems[:n_train]
    c_val = stems[n_train:n_train + n_val]
    c_test = stems[n_train + n_val:]

    train_stems.update(c_train)
    val_stems.update(c_val)
    test_stems.update(c_test)

print(f"\nImage-Level Split (Leakage-Free):")
print(f"  Train: {len(train_stems)} boards")
print(f"  Val:   {len(val_stems)} boards")
print(f"  Test:  {len(test_stems)} boards")

# Save split manifest
split_manifest = {
    "protocol": "Custom stratified image-level split on 100 VisA PCB1 anomaly images. Strictly separated by source board to prevent data leakage.",
    "seed": 42,
    "train_images": sorted(list(train_stems)),
    "val_images": sorted(list(val_stems)),
    "test_images": sorted(list(test_stems))
}

# 4. Extract crops with contextual surrounding padding
crop_data = {"train": [], "val": [], "test": []}

for img_path in all_img_files:
    stem = img_path.stem
    if stem in train_stems:
        split = "train"
    elif stem in val_stems:
        split = "val"
    elif stem in test_stems:
        split = "test"
    else:
        continue

    mask_path = mask_dir / (stem + ".png")
    if not mask_path.exists():
        continue

    rgb = np.array(Image.open(img_path).convert("RGB"))
    h_img, w_img = rgb.shape[:2]
    mask_arr = np.array(Image.open(mask_path))

    for c_val, c_name in CLASS_MAP.items():
        binary_mask = (mask_arr == c_val).astype(np.uint8)
        if binary_mask.sum() == 0:
            continue

        lbl, num_features = ndi.label(binary_mask)
        slices = ndi.find_objects(lbl)
        for sl in slices:
            if sl is None:
                continue
            y_sl, x_sl = sl
            h = y_sl.stop - y_sl.start
            w = x_sl.stop - x_sl.start
            area = int(np.count_nonzero(lbl[y_sl, x_sl] > 0))
            if area < 4 and (w * h) < 6:
                continue

            cx = int(round(x_sl.start + w / 2.0))
            cy = int(round(y_sl.start + h / 2.0))
            # Include contextual padding around the defect region
            half_w = max(32, int(w * 0.9))
            half_h = max(32, int(h * 0.9))
            pad = max(half_w, half_h, 36)

            x0 = max(0, cx - pad)
            y0 = max(0, cy - pad)
            x1 = min(w_img, cx + pad)
            y1 = min(h_img, cy + pad)

            crop = rgb[y0:y1, x0:x1]
            if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 4:
                continue

            # Standard resize to 224x224 for MobileNetV3
            crop_resized = np.array(Image.fromarray(crop).resize((224, 224), Image.BILINEAR))

            crop_data[split].append({
                "image": crop_resized,
                "label": CLASS_TO_IDX[c_name],
                "class_name": c_name,
                "source_board": stem,
                "bbox": [x_sl.start, y_sl.start, w, h],
                "area": area
            })

print("\nExtracted Contextual Defect Crops per Split:")
for split in ["train", "val", "test"]:
    counts = Counter(item["class_name"] for item in crop_data[split])
    print(f"  {split.upper():5s} ({len(crop_data[split])} crops): {dict(counts)}")

# 5. Dataset & Augmentation Pipeline
class PCBCropDataset(Dataset):
    def __init__(self, items, transform=None):
        self.items = items
        self.transform = transform

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        item = self.items[idx]
        img = Image.fromarray(item["image"])
        label = item["label"]
        if self.transform:
            img = self.transform(img)
        return img, label

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Training-only augmentations
train_transform = T.Compose([
    T.RandomHorizontalFlip(p=0.5),
    T.RandomVerticalFlip(p=0.5),
    T.RandomRotation(degrees=15),
    T.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15),
    T.ToTensor(),
    T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
])

# Inference/Evaluation preprocessing
eval_transform = T.Compose([
    T.ToTensor(),
    T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
])

train_dataset = PCBCropDataset(crop_data["train"], transform=train_transform)
val_dataset = PCBCropDataset(crop_data["val"], transform=eval_transform)
test_dataset = PCBCropDataset(crop_data["test"], transform=eval_transform)

train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True, drop_last=False)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)

# Compute class weights strictly from the training split to handle class imbalance
train_labels = [item["label"] for item in crop_data["train"]]
label_counts = Counter(train_labels)
total_train = len(train_labels)
class_weights = torch.tensor(
    [total_train / (len(CLASS_NAMES) * max(1, label_counts[i])) for i in range(len(CLASS_NAMES))],
    dtype=torch.float32
)
print(f"\nClass weights for CrossEntropyLoss: {[round(float(w), 3) for w in class_weights]}")

# 6. Model Architecture: MobileNetV3-Small Transfer Learning
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"PyTorch executing on:   {device}")

weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
model = models.mobilenet_v3_small(weights=weights)

# Replace classifier head for 4 PCB defect classes
num_features = model.classifier[0].in_features
model.classifier = nn.Sequential(
    nn.Linear(num_features, 128),
    nn.Hardswish(),
    nn.Dropout(p=0.2),
    nn.Linear(128, len(CLASS_NAMES))
)

model = model.to(device)
criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=25)

# 7. Training Loop with Validation Macro F1 Checkpointing
def evaluate(model, loader):
    model.eval()
    all_preds = []
    all_targets = []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            out = model(x)
            preds = torch.argmax(out, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(y.numpy())

    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)

    # Compute Macro F1 and per-class metrics
    per_class = {}
    f1s = []
    for i, name in enumerate(CLASS_NAMES):
        tp = np.sum((all_preds == i) & (all_targets == i))
        fp = np.sum((all_preds == i) & (all_targets != i))
        fn = np.sum((all_preds != i) & (all_targets == i))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        per_class[name] = {"precision": float(precision), "recall": float(recall), "f1": float(f1), "support": int(np.sum(all_targets == i))}
        f1s.append(f1)

    macro_f1 = float(np.mean(f1s))
    accuracy = float(np.mean(all_preds == all_targets))
    return accuracy, macro_f1, per_class, all_preds, all_targets

print("\n--- Training MobileNetV3 (25 Epochs) ---")
best_macro_f1 = -1.0
best_state = None

for epoch in range(1, 26):
    model.train()
    running_loss = 0.0
    for x, y in train_loader:
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        running_loss += loss.item() * x.size(0)

    scheduler.step()
    epoch_loss = running_loss / len(train_dataset)
    val_acc, val_f1, _, _, _ = evaluate(model, val_loader)

    if val_f1 > best_macro_f1:
        best_macro_f1 = val_f1
        best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    print(f"Epoch {epoch:2d}/25 | Train Loss: {epoch_loss:.4f} | Val Acc: {val_acc:.3f} | Val Macro F1: {val_f1:.3f} (Best: {best_macro_f1:.3f})", flush=True)

# Load best checkpoint
model.load_state_dict(best_state)
print(f"\nBest Validation Macro F1: {best_macro_f1:.4f}")

# 8. Rigorous Evaluation on the Unseen Test Set
test_acc, test_f1, test_per_class, test_preds, test_targets = evaluate(model, test_loader)
print("\n" + "=" * 50)
print(f"=== UNSEEN TEST EVALUATION (FINAL BENCHMARK) ===")
print("=" * 50)
print(f"Test Accuracy: {test_acc * 100:.2f}%")
print(f"Macro F1:      {test_f1:.4f}\n")
print(f"{'Class':<12} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}")
print("-" * 60)
for name in CLASS_NAMES:
    m = test_per_class[name]
    print(f"{name:<12} | {m['precision']:<10.3f} | {m['recall']:<10.3f} | {m['f1']:<10.3f} | {m['support']:<8d}")

# Confusion matrix
cm = np.zeros((len(CLASS_NAMES), len(CLASS_NAMES)), dtype=int)
for t, p in zip(test_targets, test_preds):
    cm[t, p] += 1

print("\nConfusion Matrix (Rows: True, Cols: Pred):")
print(f"{'':<10} " + " ".join(f"{c[:6]:>7}" for c in CLASS_NAMES))
for i, name in enumerate(CLASS_NAMES):
    row_str = " ".join(f"{cm[i, j]:>7d}" for j in range(len(CLASS_NAMES)))
    print(f"{name:<10} {row_str}")

# 9. Abstention Analysis (Selection of min_confidence)
print("\nAbstention Analysis on Validation Set:")
val_probs_all, val_targets_all = [], []
with torch.no_grad():
    for x, y in val_loader:
        probs = torch.softmax(model(x.to(device)), dim=1).cpu().numpy()
        val_probs_all.extend(probs)
        val_targets_all.extend(y.numpy())

val_probs_all = np.array(val_probs_all)
val_targets_all = np.array(val_targets_all)
val_confs = np.max(val_probs_all, axis=1)
val_preds_all = np.argmax(val_probs_all, axis=1)

# Save PyTorch checkpoint
torch.save(best_state, out_dir / "classifier_pcb1_v1.pt")
print(f"Saved PyTorch weights to: {out_dir / 'classifier_pcb1_v1.pt'}")

for thresh in [0.50, 0.60, 0.70, 0.80]:
    retained_mask = val_confs >= thresh
    if np.sum(retained_mask) > 0:
        ret_acc = np.mean(val_preds_all[retained_mask] == val_targets_all[retained_mask])
        coverage = np.mean(retained_mask)
        print(f"  Threshold {thresh:.2f} -> Coverage: {coverage*100:.1f}%, Retained Accuracy: {ret_acc*100:.1f}%")

MIN_CONFIDENCE = 0.60
print(f"Selected Abstention Setting: min_confidence = {MIN_CONFIDENCE}")

# 10. Export to ONNX
out_dir = Path("models/pcb1")
out_dir.mkdir(parents=True, exist_ok=True)
onnx_file = out_dir / "classifier_pcb1_v1.onnx"

model.eval().cpu()
dummy_input = torch.zeros(1, 3, 224, 224, dtype=torch.float32)

print(f"\nExporting MobileNetV3 to ONNX: {onnx_file}...")
torch.onnx.export(
    model,
    dummy_input,
    str(onnx_file),
    input_names=["input"],
    output_names=["logits"],
    opset_version=18,
    do_constant_folding=True
)

# Consolidate into single self-contained ONNX
onnx_mod = onnx.load(str(onnx_file), load_external_data=True)
onnx.save_model(onnx_mod, str(onnx_file), save_as_external_data=False)
data_file = onnx_file.with_name(onnx_file.name + ".data")
if data_file.exists():
    data_file.unlink()

onnx.checker.check_model(onnx_mod)
onnx_sz_mb = onnx_file.stat().st_size / (1024**2)
print(f"ONNX Model: Self-contained ({onnx_sz_mb:.2f} MB), Checker: PASSED")

# Validate with ONNX Runtime & check numerical parity
session = ort.InferenceSession(str(onnx_file), providers=["CPUExecutionProvider"])
ort_inp = session.get_inputs()[0]
ort_out = session.get_outputs()[0]
print(f"ONNX Runtime Contract: input='{ort_inp.name}' {ort_inp.shape} -> output='{ort_out.name}' {ort_out.shape}")

test_crop = crop_data["test"][0]["image"]
t_crop = eval_transform(Image.fromarray(test_crop)).unsqueeze(0)
with torch.no_grad():
    pyt_logits = model(t_crop).numpy()
ort_logits = session.run(None, {"input": t_crop.numpy()})[0]
diff = float(np.max(np.abs(pyt_logits - ort_logits)))
print(f"PyTorch vs ONNX Max Absolute Difference: {diff:.6e}")
assert diff < 1e-4, f"Divergence too high: {diff}"
print("Numerical Parity: 100% PASSED")

# Calculate SHA-256
h = hashlib.sha256()
with open(onnx_file, "rb") as f:
    while chunk := f.read(65536):
        h.update(chunk)
onnx_sha = h.hexdigest()
print(f"ONNX SHA-256: {onnx_sha}")

# 11. Write Metadata Sidecar
meta_file = out_dir / "classifier_pcb1_v1.meta.json"
meta_data = {
    "product": "PCB Controller Board",
    "model_name": "classifier-pcb1",
    "version": "1.0",
    "model_type": "classifier",
    "format": "onnx",
    "file_sha256": onnx_sha,
    "input_size": [224, 224],
    "class_names": CLASS_NAMES,
    "min_confidence": MIN_CONFIDENCE,
    "mean": IMAGENET_MEAN,
    "std": IMAGENET_STD,
    "backbone": "mobilenet_v3_small",
    "target_product": "PCB Controller Board",
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "evaluation": {
        "dataset": "Amazon VisA pcb1 (custom stratified crop split)",
        "split_counts": {
            "train_images": len(train_stems),
            "val_images": len(val_stems),
            "test_images": len(test_stems),
            "train_crops": len(crop_data["train"]),
            "val_crops": len(crop_data["val"]),
            "test_crops": len(crop_data["test"])
        },
        "test_accuracy": round(test_acc, 4),
        "macro_f1": round(test_f1, 4),
        "per_class": test_per_class,
        "confusion_matrix": cm.tolist()
    }
}

with open(meta_file, "w", encoding="utf-8") as f:
    json.dump(meta_data, f, indent=2)
print(f"Metadata sidecar written to: {meta_file}")

# Save split manifest
manifest_file = out_dir / "split_manifest.json"
with open(manifest_file, "w", encoding="utf-8") as f:
    json.dump(split_manifest, f, indent=2)
print(f"Split manifest written to: {manifest_file}")

print("\n=== VIS-A PCB1 MOBILENET-V3 DEFECT CLASSIFIER READY ===")
