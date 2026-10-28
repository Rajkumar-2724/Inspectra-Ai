"""Regenerates the synthetic DEMO images in demo_assets/. Run from backend/ with the venv active:
    python ../scripts/generate_demo_assets.py
These are programmatic drawings, not photos of real products."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.ai.demo_engine import SCENARIOS  # noqa: E402
from app.utils.synthetic import make_sample  # noqa: E402

out = root / "demo_assets"
out.mkdir(exist_ok=True)
for key in SCENARIOS:
    make_sample(key).save(out / f"demo_{key}.png")
    print("wrote", out / f"demo_{key}.png")
