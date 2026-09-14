from pathlib import Path

import pytest

pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient

from app import app

FIXTURE = Path(__file__).parent / "fixtures" / "simple_agent"

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_parse_ok():
    r = client.post("/parse", json={"repo_path": str(FIXTURE)})
    assert r.status_code == 200
    body = r.json()
    assert body["framework"] == "google-adk"
    assert any(n["name"] == "researcher" for n in body["nodes"])


def test_parse_bad_path():
    r = client.post("/parse", json={"repo_path": "/does/not/exist/xyz"})
    assert r.status_code == 400
