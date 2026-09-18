"""Outer loop that ties generator + invoker + coverage tracking together.

Phase 5 deliverable.
"""
from __future__ import annotations

from .schema import RunConfig, RunSummary


def start_run(cfg: RunConfig) -> str:
    """Kick off an async run in the background. Returns run_id immediately.
    Phase 5."""
    raise NotImplementedError("Phase 5 — see auto_probe/__init__.py")


def get_run(run_id: str) -> RunSummary:
    """Read the current state of a run — safe to poll while running."""
    raise NotImplementedError("Phase 5 — see auto_probe/__init__.py")


def cancel_run(run_id: str) -> None:
    raise NotImplementedError("Phase 5 — see auto_probe/__init__.py")
