from datetime import datetime
import threading
import time
from fastapi.testclient import TestClient

from app.main import app
from app.services.reference import next_reference_code

client = TestClient(app)

def test_bug002_reference_code_concurrency():
    # Test that next_reference_code is thread-safe
    codes = set()
    lock = threading.Lock()
    
    def worker():
        for _ in range(5):
            code = next_reference_code()
            with lock:
                codes.add(code)
            
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert len(codes) == 50, f"Expected 50 unique codes, got {len(codes)}"

def test_bug010_duplicate_username():
    org = f"acme-{datetime.now().timestamp()}"
    reg1 = client.post(
        "/auth/register",
        json={"org_name": org, "username": "bob", "password": "pw12345"},
    )
    assert reg1.status_code == 201
    
    reg2 = client.post(
        "/auth/register",
        json={"org_name": org, "username": "bob", "password": "pw12345"},
    )
    assert reg2.status_code == 409
    assert reg2.json()["code"] == "USERNAME_TAKEN"

def test_bug009_logout():
    org = f"acme-{datetime.now().timestamp()}"
    client.post(
        "/auth/register",
        json={"org_name": org, "username": "carol", "password": "pw12345"},
    )
    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "carol", "password": "pw12345"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    logout_res = client.post("/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    
    # Second logout should fail because token is revoked
    logout_res2 = client.post("/auth/logout", headers=headers)
    assert logout_res2.status_code == 401
    assert logout_res2.json()["code"] == "UNAUTHORIZED"
