import io
import os
import shutil
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="avis_test_"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{(_tmp / 'test.db').as_posix()}", "STORAGE_DIR": str(_tmp / "storage"),
    "MODELS_DIR": str(_tmp / "models"), "BATCH_INLINE": "true", "SECRET_KEY": "test-secret-key-for-pytest-only-0123456789abcdef",
    "ENVIRONMENT": "test"})
(_tmp / "models").mkdir(exist_ok=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import app.models  # noqa: E402,F401
from app.ai.model_registry import registry  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Product, ProductDefectClass, Role, User  # noqa: E402
from app.utils.synthetic import sample_png_bytes  # noqa: E402

PASSWORD = "Test-Password-123"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    registry._cache.clear()
    shutil.rmtree(_tmp / "storage", ignore_errors=True)
    for f in (_tmp / "models").glob("*"):
        if f.is_dir():
            shutil.rmtree(f, ignore_errors=True)
        else:
            f.unlink()
    db = SessionLocal()
    for name, role in (("admin", Role.admin), ("inspector", Role.inspector), ("reviewer", Role.reviewer)):
        db.add(User(email=f"{name}@t.io", username=name, full_name=name.title(), hashed_password=hash_password(PASSWORD), role=role))
    p = Product(name="Test Board", category="PCB", review_threshold=0.4, fail_threshold=0.7)
    p.defect_classes = [ProductDefectClass(name="scratch"), ProductDefectClass(name="crack")]
    db.add(p)
    db.flush()
    test_onnx = (_tmp / "models") / "test_model.onnx"
    make_onnx_model(test_onnx, size=64)
    from app.models import ModelVersion
    m = ModelVersion(name="test-patchcore", version="1.0", model_type="patchcore", format="onnx",
                     file_path="test_model.onnx", product_id=p.id)
    db.add(m)
    db.flush()
    registry.validate_and_store(db, m)
    p.patchcore_model_id = m.id
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _login(client, username):
    r = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return _login(client, "admin")


@pytest.fixture
def inspector(client):
    return _login(client, "inspector")


@pytest.fixture
def reviewer(client):
    return _login(client, "reviewer")


@pytest.fixture
def product_id():
    db = SessionLocal()
    pid = db.query(Product).first().id
    db.close()
    return pid


def png(scenario="good", seed=7) -> bytes:
    return sample_png_bytes(scenario, seed)


def do_inspect(client, headers, pid, *args, mode="real", data=None, **extra):
    files = {"file": ("sample.png", data if data is not None else png("good"), "image/png")}
    form = {"product_id": str(pid), "mode": mode, **{k: str(v) for k, v in extra.items()}}
    return client.post("/api/inspect", headers=headers, files=files, data=form)


def make_onnx_model(path: Path, size=64):
    """TEST-ONLY fixture: an untrained channel-mean graph, used to exercise the ONNX plumbing."""
    import json
    import onnx
    from onnx import TensorProto, helper
    x = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, size, size])
    y = helper.make_tensor_value_info("anomaly_map", TensorProto.FLOAT, [1, 1, size, size])
    node = helper.make_node("ReduceMean", ["input"], ["anomaly_map"], axes=[1], keepdims=1)
    g = helper.make_graph([node], "test_fixture", [x], [y])
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 8
    onnx.save(m, str(path))
    path.with_suffix(".meta.json").write_text(json.dumps({"input_size": [size, size], "score_min": -2.0, "score_max": 2.6}))
