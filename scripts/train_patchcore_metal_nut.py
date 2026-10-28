"""PatchCore Anomaly Detection Training & Export Script for MVTec AD Metal Nut.
Implements the Roth et al. (CVPR 2022) architecture with Wide ResNet-50-2.

Usage:
    python scripts/train_patchcore_metal_nut.py --dataset-dir <path_to_metal_nut> [--output-dir models/metal_nut]
"""
import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Train and export PatchCore for MVTec Metal Nut")
    parser.add_argument("--dataset-dir", type=str, default="/content/dataset/metal_nut_dataset/metal_nut",
                        help="Path to the metal_nut directory containing train/ and test/")
    parser.add_argument("--output-dir", type=str, default="models/metal_nut",
                        help="Destination directory for exported ONNX and metadata sidecar")
    parser.add_argument("--subsample-ratio", type=float, default=0.10,
                        help="Coreset subsampling ratio (default: 0.10 = 10%)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for deterministic split and coreset sampling")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Execution device: 'cuda' or 'cpu'")
    return parser.parse_args()


def main():
    args = parse_args()

    # Verify PyTorch availability
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from torch.utils.data import DataLoader, Dataset
        import torchvision.transforms as T
        from torchvision.models import wide_resnet50_2, Wide_ResNet50_2_Weights
        from sklearn.metrics import roc_auc_score, roc_curve
        from scipy.ndimage import gaussian_filter
        from PIL import Image
    except ImportError as e:
        print(f"Error: Missing dependency for training: {e}")
        print("Please install requirements: pip install torch torchvision timm scikit-learn scipy Pillow onnx onnxruntime")
        return 1

    device = torch.device("cuda" if (args.device == "cuda" and torch.cuda.is_available()) else "cpu")
    print(f"Using device: {device}")

    # Set deterministic random seed
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        torch.backends.cudnn.deterministic = True

    # Validate dataset path
    data_root = Path(args.dataset_dir)
    if not data_root.exists():
        fallbacks = [
            Path("C:/Users/rkraj/metal_nut_dataset/metal_nut"),
            Path("/content/metal_nut"),
            Path("./metal_nut")
        ]
        for fb in fallbacks:
            if fb.exists():
                data_root = fb
                break

    if not data_root.exists():
        print(f"Error: Dataset not found at '{args.dataset_dir}'.")
        return 1

    train_good_dir = data_root / "train" / "good"
    test_dir = data_root / "test"
    gt_dir = data_root / "ground_truth"

    train_images = sorted(list(train_good_dir.glob("*.png")))
    print(f"Found {len(train_images)} normal training images.")
    if len(train_images) != 220:
        print(f"Warning: Expected 220 normal training images, found {len(train_images)}")

    test_counts = {sub.name: len(list(sub.glob("*.png"))) for sub in sorted(test_dir.iterdir()) if sub.is_dir()}
    print(f"Found {sum(test_counts.values())} test images across categories: {test_counts}")

    # 176 Train / 44 Validation Split (Seed = 42)
    from sklearn.model_selection import train_test_split
    train_files, val_files = train_test_split(
        train_images,
        train_size=176,
        test_size=44,
        random_state=args.seed,
        shuffle=True
    )
    print(f"Split: {len(train_files)} training samples, {len(val_files)} validation samples.")

    IMAGE_SIZE = (256, 256)
    IMAGENET_MEAN = [0.485, 0.456, 0.406]
    IMAGENET_STD = [0.229, 0.224, 0.225]

    class MetalNutDataset(Dataset):
        def __init__(self, paths):
            self.paths = paths
            self.transform = T.Compose([
                T.Resize(IMAGE_SIZE, interpolation=T.InterpolationMode.BILINEAR),
                T.ToTensor(),
                T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
            ])

        def __len__(self):
            return len(self.paths)

        def __getitem__(self, idx):
            p = self.paths[idx]
            img = Image.open(p).convert("RGB")
            return self.transform(img), str(p)

    train_loader = DataLoader(MetalNutDataset(train_files), batch_size=16, shuffle=False)
    val_loader = DataLoader(MetalNutDataset(val_files), batch_size=16, shuffle=False)

    # Feature Extractor
    class PatchCoreFeatureExtractor(nn.Module):
        def __init__(self):
            super().__init__()
            backbone = wide_resnet50_2(weights=Wide_ResNet50_2_Weights.IMAGENET1K_V1)
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
                f2 = self.layer2(x)
                f3 = self.layer3(f2)
                p2 = self.pool(f2)
                p3 = self.pool(f3)
                p3_up = F.interpolate(p3, size=p2.shape[-2:], mode="bilinear", align_corners=False)
                return torch.cat([p2, p3_up], dim=1)

    print("Loading Wide ResNet-50-2 feature extractor...")
    extractor = PatchCoreFeatureExtractor().to(device)

    # Extract Patches
    print("Extracting patch representations from normal images...")
    patches_list = []
    for x, _ in train_loader:
        feats = extractor(x.to(device))
        B, C, H, W = feats.shape
        patches_list.append(feats.permute(0, 2, 3, 1).reshape(-1, C).cpu())
    all_patches = torch.cat(patches_list, dim=0)
    print(f"Extracted {all_patches.shape[0]} normal patch vectors.")

    # Minimax Greedy Coreset Selection
    N, D = all_patches.shape
    K = max(1, int(N * args.subsample_ratio))
    print(f"Subsampling memory bank: {N} -> {K} vectors ({args.subsample_ratio*100:.1f}% ratio)...")
    rng = np.random.RandomState(args.seed)
    p_np = all_patches.numpy()
    selected = [rng.randint(0, N)]
    min_dists = np.linalg.norm(p_np - p_np[selected[0]], axis=1)

    t0 = time.time()
    for i in range(1, K):
        best = int(np.argmax(min_dists))
        selected.append(best)
        new_d = np.linalg.norm(p_np - p_np[best], axis=1)
        min_dists = np.minimum(min_dists, new_d)
        if (i + 1) % 500 == 0 or (i + 1) == K:
            print(f"  Selected {i+1}/{K} ({time.time()-t0:.1f}s)...")

    memory_bank = all_patches[selected]
    print(f"Normal feature memory bank built: {memory_bank.shape}")

    # Inference Model
    class PatchCoreInference(nn.Module):
        def __init__(self, ext, mb):
            super().__init__()
            self.ext = ext
            self.register_buffer("memory_bank", mb)

        def forward(self, x):
            B, _, H, W = x.shape
            feats = self.ext(x)
            B, C, hp, wp = feats.shape
            patches = feats.permute(0, 2, 3, 1).reshape(-1, C)
            dists = torch.cdist(patches, self.memory_bank)
            min_d, _ = dists.min(dim=-1)
            amap = min_d.reshape(B, 1, hp, wp)
            amap_up = F.interpolate(amap, size=(H, W), mode="bilinear", align_corners=False)
            score = min_d.reshape(B, -1).max(dim=-1).values
            return amap_up, score

    model = PatchCoreInference(extractor, memory_bank.to(device)).to(device).eval()

    # Validation Calibration
    val_scores = []
    with torch.no_grad():
        for x, _ in val_loader:
            _, sc = model(x.to(device))
            val_scores.extend(sc.cpu().tolist())

    val_scores = np.array(val_scores)
    val_mean = float(np.mean(val_scores))
    val_std = float(np.std(val_scores))
    val_min = float(np.min(val_scores))
    SCORE_MIN = float(max(0.0, round(val_min * 0.95, 3)))
    SCORE_MAX = float(round(val_mean + 6.0 * val_std, 3))
    if SCORE_MAX <= SCORE_MIN:
        SCORE_MAX = SCORE_MIN + 10.0

    print(f"Calibration on 44 Validation Normal Images: score_min={SCORE_MIN}, score_max={SCORE_MAX}")

    # Evaluate on Official Held-Out Test Set
    test_records = []
    for cat in test_counts.keys():
        sub = test_dir / cat
        for p in sorted(sub.glob("*.png")):
            is_def = (cat != "good")
            mask_p = (gt_dir / cat / (p.stem + "_mask.png")) if is_def else None
            test_records.append({"path": p, "category": cat, "is_defective": is_def, "mask": mask_p})

    print(f"Evaluating frozen model on {len(test_records)} official test samples...")
    y_true, y_score = [], []
    pixel_true, pixel_score = [], []
    by_category = {c: [] for c in test_counts.keys()}

    with torch.no_grad():
        for rec in test_records:
            from PIL import Image
            img = Image.open(rec["path"]).convert("RGB")
            t_img = T.Compose([
                T.Resize(IMAGE_SIZE),
                T.ToTensor(),
                T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
            ])(img).unsqueeze(0).to(device)

            amap, sc = model(t_img)
            amap_np = gaussian_filter(amap.squeeze().cpu().numpy(), sigma=4)
            raw_s = float(sc.cpu().item())
            norm_s = float(np.clip((raw_s - SCORE_MIN) / (SCORE_MAX - SCORE_MIN), 0.0, 1.0))

            y_true.append(1 if rec["is_defective"] else 0)
            y_score.append(norm_s)
            by_category[rec["category"]].append(norm_s)

            if rec["mask"] and rec["mask"].exists():
                import cv2
                gt_m = cv2.imread(str(rec["mask"]), cv2.IMREAD_GRAYSCALE)
                gt_res = (cv2.resize(gt_m, IMAGE_SIZE) > 128).astype(np.uint8)
                pixel_true.extend(gt_res.flatten())
                pixel_score.extend(amap_np.flatten())
            elif not rec["is_defective"]:
                pixel_true.extend(np.zeros(IMAGE_SIZE[0] * IMAGE_SIZE[1], dtype=np.uint8))
                pixel_score.extend(amap_np.flatten())

    y_true = np.array(y_true)
    y_score = np.array(y_score)
    image_auroc = float(roc_auc_score(y_true, y_score))
    pixel_auroc = float(roc_auc_score(pixel_true, pixel_score)) if pixel_true else None

    print("\n" + "="*50)
    print("ACTUAL MEASURED TEST METRICS")
    print("="*50)
    print(f"Image-Level AUROC: {image_auroc*100:.2f}%")
    if pixel_auroc:
        print(f"Pixel-Level AUROC: {pixel_auroc*100:.2f}%")
    for cat, scs in by_category.items():
        print(f"  {cat:10s} (N={len(scs)}): Mean Score={np.mean(scs):.4f}")
    print("="*50)

    # Export ONNX and Metadata Sidecar
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_file = out_dir / "patchcore_metal_nut_v1.onnx"
    meta_file = out_dir / "patchcore_metal_nut_v1.meta.json"
    report_file = out_dir / "evaluation_report.json"

    class ONNXWrapper(nn.Module):
        def __init__(self, core_model):
            super().__init__()
            self.core = core_model

        def forward(self, x):
            amap, _ = self.core(x)
            return amap

    export_model = ONNXWrapper(model).cpu().eval()
    dummy_input = torch.zeros(1, 3, 256, 256, dtype=torch.float32)

    print(f"Exporting ONNX model to {onnx_file}...")
    torch.onnx.export(
        export_model,
        dummy_input,
        str(onnx_file),
        input_names=["input"],
        output_names=["anomaly_map"],
        opset_version=14
    )

    meta_payload = {
        "input_size": list(IMAGE_SIZE),
        "score_min": SCORE_MIN,
        "score_max": SCORE_MAX,
        "mean": IMAGENET_MEAN,
        "std": IMAGENET_STD,
        "backbone": "wide_resnet50_2",
        "target_product": "Metal Nut",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": {
            "image_auroc": round(image_auroc, 4),
            "pixel_auroc": round(pixel_auroc, 4) if pixel_auroc else None,
            "test_samples": len(y_true)
        }
    }
    meta_file.write_text(json.dumps(meta_payload, indent=2))

    report_payload = {
        "system": "AI-Visual-Inspection Platform",
        "dataset": "MVTec AD Metal Nut",
        "model_architecture": "PatchCore (Wide ResNet-50-2)",
        "train_samples": len(train_files),
        "val_samples": len(val_files),
        "test_samples": len(y_true),
        "test_breakdown": test_counts,
        "calibration": {
            "score_min": SCORE_MIN,
            "score_max": SCORE_MAX,
            "val_mean": val_mean,
            "val_std": val_std
        },
        "metrics": {
            "image_auroc": round(image_auroc, 4),
            "pixel_auroc": round(pixel_auroc, 4) if pixel_auroc else None,
            "category_means": {k: round(float(np.mean(v)), 4) for k, v in by_category.items()}
        }
    }
    report_file.write_text(json.dumps(report_payload, indent=2))

    print(f"Export complete!\n- ONNX: {onnx_file}\n- Metadata: {meta_file}\n- Report: {report_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
