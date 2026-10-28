"""Setup and integration script for Plain Paper anomaly detection.
Initializes the 'Plain Paper' product, registers the PatchCore model artifact,
sets up the nominal reference image, and enables Real AI inspection.

Usage:
    python -m app.scripts.setup_paper
"""
import json
import shutil
import sys
from pathlib import Path

from sqlalchemy import select

from app.ai.model_registry import registry, resolve_model_path
from app.core.config import get_settings
from app.database.migrate import upgrade_head
from app.database.session import SessionLocal
from app.models import ModelStatus, ModelVersion, Product, ProductDefectClass


def setup_paper():
    upgrade_head()
    s = get_settings()
    db = SessionLocal()

    try:
        print("1. Checking 'Plain Paper' product in database...")
        prod = db.execute(select(Product).where(Product.name == "Plain Paper")).scalar_one_or_none()
        if not prod:
            prod = Product(
                name="Plain Paper",
                category="Paper manufacturing",
                description="Plain white paper surface defect and dot anomaly inspection.",
                review_threshold=0.40,
                fail_threshold=0.70
            )
            prod.defect_classes = [
                ProductDefectClass(name="dot"),
                ProductDefectClass(name="contamination"),
                ProductDefectClass(name="surface_blemish"),
            ]
            db.add(prod)
            db.commit()
            db.refresh(prod)
            print(f"  Created 'Plain Paper' product (ID: {prod.id}) with 3 defect classes.")
        else:
            print(f"  'Plain Paper' already exists (ID: {prod.id}).")

        # Reference image setup
        dataset_good = Path(r"C:\Users\rkraj\paper_dataset\train\good\0bdedfdc-f724-48ad-8a24-9c176da13c30.jpg")
        if not prod.reference_image_path or not (s.storage_path / prod.reference_image_path).is_file():
            rel = f"products/{prod.id}/reference.jpg"
            dest = s.storage_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dataset_good.is_file():
                shutil.copy(dataset_good, dest)
                print(f"  Copied reference image from {dataset_good.name} to {dest}")
            prod.reference_image_path = rel
            db.commit()

        # Check model files
        models_dir = s.models_path
        paper_dir = models_dir / "paper"
        onnx_file = paper_dir / "paper_patchcore_v1.onnx"
        meta_file = paper_dir / "paper_patchcore_v1.meta.json"

        if not onnx_file.is_file() or not meta_file.is_file():
            print(f"  WARNING: Model artifact not yet present at {onnx_file}")
            return 1
        else:
            print(f"2. Verified model artifacts at {onnx_file} ({onnx_file.stat().st_size / (1024*1024):.2f} MB)")

        # Update registry.yaml
        registry_yaml = models_dir / "registry.yaml"
        current_yaml = registry_yaml.read_text(encoding="utf-8") if registry_yaml.is_file() else ""
        
        # Check if patchcore-paper is already listed
        if "patchcore-paper" not in current_yaml:
            print("3. Adding patchcore-paper to models/registry.yaml...")
            new_entry = """  - name: patchcore-paper
    version: "1.0"
    type: patchcore
    format: onnx
    file: paper/paper_patchcore_v1.onnx
    product: "Plain Paper"
    assign: true
"""
            if "models:" in current_yaml:
                updated_yaml = current_yaml.rstrip() + "\n" + new_entry
            else:
                updated_yaml = "models:\n" + new_entry
            registry_yaml.write_text(updated_yaml, encoding="utf-8")
        else:
            print("3. models/registry.yaml already contains patchcore-paper.")

        # Register in Database
        print("4. Validating and registering model in database...")
        m = db.execute(select(ModelVersion).where(ModelVersion.name == "patchcore-paper", ModelVersion.version == "1.0")).scalar_one_or_none()
        if not m:
            m = ModelVersion(
                name="patchcore-paper",
                version="1.0",
                model_type="patchcore",
                format="onnx",
                file_path="paper/paper_patchcore_v1.onnx"
            )
            db.add(m)
            db.flush()

        m.product_id = prod.id
        registry.validate_and_store(db, m)

        if m.status == ModelStatus.READY:
            prod.patchcore_model_id = m.id
            db.commit()
            print(f"  Model registered as READY! Assigned to 'Plain Paper' (Product ID: {prod.id}).")
        else:
            db.commit()
            print(f"  Warning: Model status is {m.status.value}: {m.status_detail}")

        # Verify Product Readiness
        readiness = registry.product_readiness(db, prod)
        overall = registry.overall(db)
        print("\n" + "="*55)
        print(f"Plain Paper Real AI Ready: {readiness['ready']} (Version: {readiness['version']})")
        print(f"Overall Real AI Mode Available: {overall['real_mode_available']}")
        print("="*55)
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(setup_paper())
