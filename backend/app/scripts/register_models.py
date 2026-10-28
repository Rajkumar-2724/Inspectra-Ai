"""Register model artifacts listed in models/registry.yaml (copy from registry.example.yaml).
Usage (from backend/):  python -m app.scripts.register_models
Each entry is validated for real (file, metadata sidecar, shapes, forward pass); nothing is marked READY unless it is."""
import sys

import yaml
from sqlalchemy import select

from app.core.config import get_settings
from app.database.migrate import upgrade_head
from app.database.session import SessionLocal
from app.ai.model_registry import registry
from app.models import ModelVersion, Product


def main() -> int:
    cfg = get_settings().models_path / "registry.yaml"
    if not cfg.is_file():
        print(f"{cfg} not found. Copy models/registry.example.yaml to models/registry.yaml and edit it.")
        return 1
    upgrade_head()
    entries = (yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}).get("models", [])
    db = SessionLocal()
    try:
        for e in entries:
            prod = db.execute(select(Product).where(Product.name == e.get("product"))).scalar_one_or_none() if e.get("product") else None
            if e.get("product") and not prod:
                print(f"SKIP {e['name']}: product '{e['product']}' does not exist")
                continue
            m = db.execute(select(ModelVersion).where(ModelVersion.name == e["name"], ModelVersion.version == str(e["version"]))).scalar_one_or_none()
            if not m:
                m = ModelVersion(name=e["name"], version=str(e["version"]), model_type=e["type"], format=e["format"], file_path=e["file"])
                db.add(m)
                db.flush()
            m.product_id = prod.id if prod else None
            registry.validate_and_store(db, m)
            if prod and e.get("assign", True) and m.status.value == "READY":
                setattr(prod, "patchcore_model_id" if m.model_type == "patchcore" else "classifier_model_id", m.id)
            print(f"{m.name} v{m.version}: {m.status.value} - {m.status_detail}")
        db.commit()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
