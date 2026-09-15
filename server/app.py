import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adk_parser import Trace, classify, parse_path, run_probe, merge_runtime
from adk_parser.codegen import EmitSkipped, apply_region, emit_layout, emit_python

app = FastAPI(title="AgentBuilder Parser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _allowed_roots() -> list[Path]:
    """Resolved absolute roots the endpoints are permitted to read.

    Read from ``AGENTBUILDER_ALLOWED_ROOTS`` (colon-separated on POSIX,
    semicolon on Windows via os.pathsep). Empty/unset means permissive
    mode — every path is allowed. Intended default for local dev; a
    deployed instance should set this.
    """
    raw = os.environ.get("AGENTBUILDER_ALLOWED_ROOTS", "").strip()
    if not raw:
        return []
    roots: list[Path] = []
    for part in raw.split(os.pathsep):
        p = part.strip()
        if not p:
            continue
        try:
            roots.append(Path(p).expanduser().resolve())
        except (OSError, RuntimeError):
            continue
    return roots


def _resolve_repo_path(raw: str) -> Path:
    """Resolve + validate ``raw`` against the allowlist. 400 if bad, 403 if
    outside every allowed root."""
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    allowed = _allowed_roots()
    if allowed:
        for base in allowed:
            try:
                root.relative_to(base)
                return root
            except ValueError:
                continue
        raise HTTPException(
            status_code=403,
            detail=f"path {root} is outside AGENTBUILDER_ALLOWED_ROOTS",
        )
    return root


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
    root = _resolve_repo_path(req.repo_path)
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
    root = _resolve_repo_path(req.repo_path)
    return run_probe(root, req.entry_module, timeout=req.timeout)


class EmitRequest(BaseModel):
    repo_path: str


@app.post("/emit")
def emit(req: EmitRequest):
    root = _resolve_repo_path(req.repo_path)
    graph = parse_path(root)
    try:
        source = emit_python(graph)
    except EmitSkipped as e:
        raise HTTPException(status_code=422, detail=f"emit skipped: {e}")
    return {"source": source, "framework": graph.framework, "version": graph.version}


class EmitLayoutRequest(BaseModel):
    repo_path: str
    # If True the endpoint reads each target file (if present under repo_path)
    # and returns the merged result via apply_region. If False it returns
    # region bodies only — the caller merges.
    merge: bool = True


@app.post("/emit-layout")
def emit_layout_endpoint(req: EmitLayoutRequest):
    root = _resolve_repo_path(req.repo_path)
    graph = parse_path(root)
    try:
        bodies = emit_layout(graph)
    except EmitSkipped as e:
        raise HTTPException(status_code=422, detail=f"emit skipped: {e}")

    files: dict[str, str] = {}
    for rel, body in bodies.items():
        if req.merge:
            target = root / rel
            existing = target.read_text() if target.exists() else ""
            files[rel] = apply_region(existing, body)
        else:
            files[rel] = body
    return {
        "files": files,
        "merged": req.merge,
        "framework": graph.framework,
        "version": graph.version,
    }


class TraceRequest(BaseModel):
    repo_path: str
    trace: Trace


@app.post("/traces")
def traces(req: TraceRequest):
    root = _resolve_repo_path(req.repo_path)
    graph = parse_path(root)
    merged = classify(graph, req.trace)
    return merged.model_dump()


@app.get("/health")
def health():
    return {"ok": True}
