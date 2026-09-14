from pathlib import Path

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


@app.post("/parse")
def parse(req: ParseRequest):
    root = Path(req.repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    return parse_path(root).model_dump()


@app.get("/health")
def health():
    return {"ok": True}
