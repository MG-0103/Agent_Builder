"""Multi-turn session lifecycle: open, invoke repeatedly, close.

Phase 4 deliverable.
"""
from __future__ import annotations

from typing import Any

from .schema import RunConfig, SessionRecord


def open_session(cfg: RunConfig) -> str:
    """Return a new session_id and prime any state the invoker needs to
    resume across turns. Phase 4."""
    raise NotImplementedError("Phase 4 — see auto_probe/__init__.py")


def run_session(
    cfg: RunConfig,
    session_id: str,
    target_edges: list[str],
    graph: dict[str, Any],
) -> SessionRecord:
    """Run a full multi-turn session against `session_id`, ending on turn
    budget or generator-says-end or terminal agent response. Phase 4."""
    raise NotImplementedError("Phase 4 — see auto_probe/__init__.py")


def close_session(session_id: str) -> None:
    raise NotImplementedError("Phase 4 — see auto_probe/__init__.py")
