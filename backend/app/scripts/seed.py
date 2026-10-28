"""Development-only setup.  python -m app.scripts.seed

Creates the admin user from ADMIN_* env vars and base products. Demo inspections are omitted."""
import argparse
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models import Product, ProductDefectClass, Role, User
from app.utils.synthetic import make_sample

PRODUCTS = [
    ("PCB Controller Board", "PCB", ["scratch", "crack", "missing_component"], 0.40, 0.70),
    ("Metal Bracket", "Metal surface", ["scratch", "dent", "rust"], 0.40, 0.70),
    ("Bottle Cap", "Bottle or cap", ["crack", "deformation"], 0.35, 0.65),
    ("Metal Nut", "Machined fastener", ["bent", "color", "flip", "scratch"], 0.40, 0.70),
]


def main() -> int:
    s = get_settings()
    if s.is_production:
        print("Refusing to run seed in production.")
        return 1
    if not s.ADMIN_PASSWORD or len(s.ADMIN_PASSWORD) < 8:
        print("Set ADMIN_PASSWORD (>= 8 chars) in backend/.env first.")
        return 1
    from app.database.migrate import upgrade_head
    upgrade_head()
    db = SessionLocal()
    try:
        if not db.execute(select(User).where(User.username == s.ADMIN_USERNAME)).scalar_one_or_none():
            db.add(User(email=s.ADMIN_EMAIL.lower(), username=s.ADMIN_USERNAME, full_name="Administrator",
                        hashed_password=hash_password(s.ADMIN_PASSWORD), role=Role.admin))
            print(f"Created admin user '{s.ADMIN_USERNAME}'")
        for u, role in (("inspector", Role.inspector), ("reviewer", Role.reviewer)):
            if not db.execute(select(User).where(User.username == u)).scalar_one_or_none():
                db.add(User(email=f"{u}@example.com", username=u, full_name=u.title(), hashed_password=hash_password(s.ADMIN_PASSWORD), role=role))
                print(f"Created {role.value} user '{u}' (same password as admin; development only)")
        for name, cat, classes, rv, fl in PRODUCTS:
            if not db.execute(select(Product).where(Product.name == name)).scalar_one_or_none():
                p = Product(name=name, category=cat, description=f"Industrial product ({cat})", review_threshold=rv, fail_threshold=fl)
                p.defect_classes = [ProductDefectClass(name=c) for c in classes]
                db.add(p)
        db.commit()
        prods = db.execute(select(Product)).scalars().all()
        for p in prods:  # a reference image enables the reference-patch explanation
            if not p.reference_image_path:
                from app.services.inspection_service import storage_file
                rel = f"products/{p.id}/reference.png"
                path = storage_file(rel)
                path.parent.mkdir(parents=True, exist_ok=True)
                make_sample("good").save(path, "PNG")
                p.reference_image_path = rel
        db.commit()
        print("Seed complete.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
