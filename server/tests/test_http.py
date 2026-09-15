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


def test_parse_cache_returns_same_object():
    r1 = client.post("/parse", json={"repo_path": str(FIXTURE)})
    r2 = client.post("/parse", json={"repo_path": str(FIXTURE)})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


def test_parse_cache_invalidates_on_mtime_change(tmp_path):
    import shutil
    # Copy the fixture into a scratch dir so we can mutate it.
    scratch = tmp_path / "proj"
    shutil.copytree(FIXTURE, scratch)
    r1 = client.post("/parse", json={"repo_path": str(scratch)}).json()
    n1 = len(r1["nodes"])

    # Add a new agent module -> mtime moves -> cache miss.
    (scratch / "extra.py").write_text(
        "from google.adk.agents import LlmAgent\n"
        "extra = LlmAgent(name='extra', model='m', instruction='e')\n"
    )
    r2 = client.post("/parse", json={"repo_path": str(scratch)}).json()
    assert len(r2["nodes"]) > n1


PROBE_FIXTURE = Path(__file__).parent / "fixtures" / "runtime_probe"


def test_probe_endpoint():
    r = client.post("/probe", json={"repo_path": str(PROBE_FIXTURE), "entry_module": "agent"})
    assert r.status_code == 200
    body = r.json()
    names = {n["name"] for n in body["nodes"]}
    assert {"researcher", "writer", "pipeline"} <= names


def test_emit_endpoint():
    r = client.post("/emit", json={"repo_path": str(FIXTURE)})
    assert r.status_code == 200
    body = r.json()
    assert "LlmAgent" in body["source"]
    assert "researcher" in body["source"]


def test_emit_skipped_returns_422():
    r = client.post(
        "/emit",
        json={"repo_path": str(Path(__file__).parent / "fixtures" / "custom_agent")},
    )
    assert r.status_code == 422


def test_parse_with_entry_module_merges_probe():
    r = client.post("/parse", json={"repo_path": str(PROBE_FIXTURE), "entry_module": "agent"})
    assert r.status_code == 200
    body = r.json()
    # Runtime discovered researcher/writer/pipeline; none exist statically here
    # (this fixture uses plain classes, not the ADK LlmAgent import), so they
    # arrive as runtime-only nodes tagged observed.
    names = {n["name"] for n in body["nodes"]}
    assert {"researcher", "writer", "pipeline"} <= names
    runtime_only = [n for n in body["nodes"] if n["meta"].get("runtime_only")]
    assert len(runtime_only) >= 3
