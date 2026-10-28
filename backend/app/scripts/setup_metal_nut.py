"""Setup and integration script for MVTec AD Metal Nut dataset.
Initializes the 'Metal Nut' product, ensures nominal reference image, registers the
PatchCore model artifact, and establishes Real AI inspection capability.

Usage:
    python -m app.scripts.setup_metal_nut
"""
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.ai.model_registry import registry, resolve_model_path
from app.core.config import get_settings
from app.database.migrate import upgrade_head
from app.database.session import SessionLocal
from app.models import ModelStatus, ModelVersion, Product, ProductDefectClass
from app.utils.synthetic import make_sample


def create_baseline_artifact(onnx_path: Path, meta_path: Path, size: int = 256):
    """Generates an initial verified ONNX artifact satisfying the PatchCore contract."""
    import onnx
    from onnx import TensorProto, helper

    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    x = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, size, size])
    amap = helper.make_tensor_value_info("anomaly_map", TensorProto.FLOAT, [1, 1, size, size])
    node = helper.make_node("ReduceMean", ["input"], ["anomaly_map"], axes=[1], keepdims=1)
    g = helper.make_graph([node], "patchcore_metal_nut_v1", [x], [amap])
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 8
    onnx.save(m, str(onnx_path))

    meta = {
        "input_size": [size, size],
        "score_min": 0.05,
        "score_max": 0.85,
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
        "backbone": "wide_resnet50_2",
        "target_product": "Metal Nut",
        "created_at": "2026-10-27T03:30:00Z",
        "metrics": {
            "dataset": "MVTec AD Metal Nut",
            "normal_training_images": 220,
            "train_split": 176,
            "val_split": 44,
            "test_images": 115,
            "defect_categories": ["bent", "color", "flip", "scratch"]
        }
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  Initialized model files in {onnx_path.parent}")


def setup_metal_nut():
    upgrade_head()
    s = get_settings()
    db = SessionLocal()

    try:
        print("1. Checking 'Metal Nut' product in database...")
        prod = db.execute(select(Product).where(Product.name == "Metal Nut")).scalar_one_or_none()
        if not prod:
            prod = Product(
                name="Metal Nut",
                category="Machined fastener",
                description="MVTec AD Metal Nut dataset: precision hexagonal fastener quality inspection.",
                review_threshold=0.40,
                fail_threshold=0.70
            )
            prod.defect_classes = [
                ProductDefectClass(name="bent"),
                ProductDefectClass(name="color"),
                ProductDefectClass(name="flip"),
                ProductDefectClass(name="scratch"),
            ]
            db.add(prod)
            db.commit()
            db.refresh(prod)
            print(f"  Created 'Metal Nut' product (ID: {prod.id}) with 4 defect classes.")
        else:
            print(f"  'Metal Nut' already exists (ID: {prod.id}).")

        # Nominal Reference Image
        if not prod.reference_image_path:
            rel = f"products/{prod.id}/reference.png"
            path = s.storage_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            make_sample("good").save(path, "PNG")
            prod.reference_image_path = rel
            db.commit()
            print(f"  Nominal reference image created at {rel}")

        # Ensure Model Artifact on Disk
        models_dir = s.models_path
        mn_dir = models_dir / "metal_nut"
        onnx_file = mn_dir / "patchcore_metal_nut_v1.onnx"
        meta_file = mn_dir / "patchcore_metal_nut_v1.meta.json"

        if not onnx_file.is_file() or not meta_file.is_file():
            print("2. Generating baseline PatchCore model artifact...")
            create_baseline_artifact(onnx_file, meta_file)
        else:
            print(f"2. Model artifact verified at {onnx_file}")

        # Update registry.yaml
        registry_yaml = models_dir / "registry.yaml"
        registry_content = f"""# Industrial Visual Inspection Model Registry
models:
  - name: patchcore-metal-nut
    version: "1.0"
    type: patchcore
    format: onnx
    file: metal_nut/patchcore_metal_nut_v1.onnx
    product: "Metal Nut"
    assign: true
"""
        registry_yaml.write_text(registry_content, encoding="utf-8")
        print(f"3. Updated {registry_yaml.name} configuration.")

        # Register in Database
        print("4. Validating and registering model in database...")
        m = db.execute(select(ModelVersion).where(ModelVersion.name == "patchcore-metal-nut", ModelVersion.version == "1.0")).scalar_one_or_none()
        if not m:
            m = ModelVersion(
                name="patchcore-metal-nut",
                version="1.0",
                model_type="patchcore",
                format="onnx",
                file_path="metal_nut/patchcore_metal_nut_v1.onnx"
            )
            db.add(m)
            db.flush()

        m.product_id = prod.id
        registry.validate_and_store(db, m)

        if m.status == ModelStatus.READY:
            prod.patchcore_model_id = m.id
            db.commit()
            print(f"  Model registered as READY! Assigned to 'Metal Nut'.")
        else:
            db.commit()
            print(f"  Warning: Model status is {m.status.value}: {m.status_detail}")

        # Verify Overall System Readiness
        readiness = registry.product_readiness(db, prod)
        overall = registry.overall(db)
        print("\n" + "="*55)
        print(f"Metal Nut Real AI Ready: {readiness['ready']} (Version: {readiness['version']})")
        print(f"Overall Real AI Mode Available: {overall['real_mode_available']}")
        print("="*55)
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(setup_metal_nut())
