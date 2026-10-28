from tests.conftest import PASSWORD


def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"email": "new@t.io", "username": "newuser", "password": "Abcdef123!"})
    assert r.status_code == 201 and r.json()["role"] == "inspector"
    assert "hashed_password" not in r.json()
    tok = client.post("/api/auth/login", json={"username": "newuser", "password": "Abcdef123!"}).json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200 and me.json()["username"] == "newuser"


def test_duplicate_and_weak_password(client):
    assert client.post("/api/auth/register", json={"email": "x@t.io", "username": "inspector", "password": "Abcdef123!"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "y@t.io", "username": "yy1", "password": "short"}).status_code == 422


def test_wrong_password_and_protection(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_self_registration_cannot_pick_role(client):
    r = client.post("/api/auth/register", json={"email": "z@t.io", "username": "zed", "password": "Abcdef123!", "role": "admin"})
    assert r.json()["role"] == "inspector"


def test_change_password(client, inspector):
    assert client.post("/api/auth/change-password", headers=inspector, json={"current_password": "bad", "new_password": "Newpass-1234"}).status_code == 400
    assert client.post("/api/auth/change-password", headers=inspector, json={"current_password": PASSWORD, "new_password": "Newpass-1234"}).status_code == 204
    assert client.post("/api/auth/login", json={"username": "inspector", "password": "Newpass-1234"}).status_code == 200


def test_role_permissions(client, admin, inspector, reviewer, product_id):
    body = {"name": "P2", "category": "PCB"}
    assert client.post("/api/products", headers=inspector, json=body).status_code == 403
    assert client.post("/api/products", headers=reviewer, json=body).status_code == 403
    assert client.post("/api/products", headers=admin, json=body).status_code == 201
    assert client.get("/api/users", headers=inspector).status_code == 403
    assert client.get("/api/audit/verify", headers=inspector).status_code == 403
    assert client.post("/api/models/register", headers=inspector, json={"name": "m", "version": "1", "model_type": "patchcore", "format": "onnx", "file_path": "a.onnx"}).status_code == 403
    r = client.post("/api/inspect", headers=reviewer, files={"file": ("a.png", b"x", "image/png")}, data={"product_id": str(product_id)})
    assert r.status_code == 403
