import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adk_parser import parse_path, run_probe, merge_runtime
from adk_parser.codegen import EmitSkipped, emit_python

app = FastAPI(title="AgentBuilder Parser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    repo_path: str
    entry_module: str | None = None  # If set, merge runtime probe into result.


class ProbeRequest(BaseModel):
    repo_path: str
    entry_module: str
    timeout: float = 30.0


_cache: dict[tuple[str, float, str], dict[str, Any]] = {}


def _max_mtime(root: Path) -> float:
    """Newest mtime across all .py files under root; 0.0 if empty."""
    best = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                try:
                    m = (Path(dirpath) / fn).stat().st_mtime
                except OSError:
                    continue
                if m > best:
                    best = m
    return best


@app.post("/parse")
def parse(req: ParseRequest):
    root = Path(req.repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    key = (str(root), _max_mtime(root), req.entry_module or "")
    hit = _cache.get(key)
    if hit is not None:
        return hit
    graph = parse_path(root)
    if req.entry_module:
        observed = run_probe(root, req.entry_module)
        merge_runtime(graph, observed)
    result = graph.model_dump()
    _cache[key] = result
    return result


@app.post("/probe")
def probe(req: ProbeRequest):
    root = Path(req.repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    return run_probe(root, req.entry_module, timeout=req.timeout)


class EmitRequest(BaseModel):
    repo_path: str


@app.post("/emit")
def emit(req: EmitRequest):
    root = Path(req.repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    graph = parse_path(root)
    try:
        source = emit_python(graph)
    except EmitSkipped as e:
        raise HTTPException(status_code=422, detail=f"emit skipped: {e}")
    return {"source": source, "framework": graph.framework, "version": graph.version}


@app.get("/health")
def health():
    return {"ok": True}
