import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adk_parser import parse_path

app = FastAPI(title="AgentBuilder Parser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    repo_path: str


_cache: dict[tuple[str, float], dict[str, Any]] = {}


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
    key = (str(root), _max_mtime(root))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    result = parse_path(root).model_dump()
    _cache[key] = result
    return result


@app.get("/health")
def health():
    return {"ok": True}
