"""Sanity tests for the auto-probe scaffolding. Each endpoint should be
routed and reachable, and return 501 with a helpful message until the phase
that implements it lands."""
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_invoke_endpoint_registered_and_501s():
    r = client.post(
        "/explore/invoke",
        json={
            "repo_path": "/tmp",
            "entry_module": "x",
            "query": "hi",
        },
    )
    assert r.status_code == 501
    body = r.json()
    assert "Phase 1" in body["detail"]


def test_run_endpoint_registered_and_501s():
    r = client.post(
        "/explore/run",
        json={"repo_path": "/tmp", "entry_module": "x"},
    )
    assert r.status_code == 501
    assert "Phase 5" in r.json()["detail"]


def test_status_endpoint_registered_and_501s():
    r = client.get("/explore/status/nope")
    assert r.status_code == 501
