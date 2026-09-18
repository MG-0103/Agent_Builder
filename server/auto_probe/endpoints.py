"""FastAPI endpoints for the auto-probe. Wired into the top-level app via
`app.include_router(router)`. Each endpoint returns 501 until the phase that
implements its handler lands."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .invoker import NotImplementedYet, invoke_once
from .orchestrator import get_run, start_run
from .schema import InvokeRequest, RunConfig

router = APIRouter(prefix="/explore", tags=["auto_probe"])


@router.post("/invoke")
def explore_invoke(req: InvokeRequest):
    """Run a single query against the target agent in a session. Returns the
    captured trace. Phase 1 wires this up; until then it 501s."""
    try:
        return invoke_once(req)
    except NotImplementedYet as e:
        raise HTTPException(status_code=501, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.post("/run")
def explore_run(cfg: RunConfig):
    """Kick off a full auto-probe run: generator + orchestrator + coverage
    tracking. Async — returns {run_id} immediately, poll /status/{run_id}."""
    try:
        run_id = start_run(cfg)
        return {"run_id": run_id}
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.get("/status/{run_id}")
def explore_status(run_id: str):
    """Poll the current state of a run — coverage %, session summaries, etc."""
    try:
        return get_run(run_id)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
