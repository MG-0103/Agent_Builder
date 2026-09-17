import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adk_parser import Trace, classify, parse_path, run_probe, merge_runtime
from adk_parser.codegen import EmitSkipped, apply_region, emit_layout, emit_python
from adk_parser.entry_candidates import rank_entry_candidates

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


def _strip_path_quotes(raw: str) -> str:
    """Strip surrounding matching quotes and whitespace. Users pasting a
    path from a Windows or macOS shell frequently include them."""
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1].strip()
    return s


def _resolve_repo_path(raw: str) -> Path:
    """Resolve + validate ``raw`` against the allowlist. 400 if bad, 403 if
    outside every allowed root."""
    root = Path(_strip_path_quotes(raw)).expanduser().resolve()
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
    entry_object: str | None = None  # Optional name of a factory / root inside entry_module.


class ProbeRequest(BaseModel):
    repo_path: str
    entry_module: str
    entry_object: str | None = None
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
    key = (str(root), _max_mtime(root), req.entry_module or "", req.entry_object or "")
    hit = _cache.get(key)
    if hit is not None:
        return hit
    graph = parse_path(root)
    probe_failed = False
    if req.entry_module:
        observed = run_probe(root, req.entry_module, entry_object=req.entry_object)
        merge_runtime(graph, observed)
        probe_failed = bool(observed.get("errors"))
    result = graph.model_dump()
    if not probe_failed:
        _cache[key] = result
    return result


@app.post("/probe")
def probe(req: ProbeRequest):
    root = _resolve_repo_path(req.repo_path)
    return run_probe(
        root,
        req.entry_module,
        timeout=req.timeout,
        entry_object=req.entry_object,
    )


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


class EntryCandidatesRequest(BaseModel):
    repo_path: str
    limit: int = 10


@app.post("/entry-candidates")
def entry_candidates(req: EntryCandidatesRequest):
    root = _resolve_repo_path(req.repo_path)
    candidates = rank_entry_candidates(root, limit=req.limit)
    return {"candidates": [c.to_dict() for c in candidates]}


@app.get("/health")
def health():
    return {"ok": True}
