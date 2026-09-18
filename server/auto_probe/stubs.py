"""Tool stubbing strategies for the auto-probe.

Phase 2 deliverable. Placeholder now so downstream modules can import the
`Stub` type.
"""
from __future__ import annotations

from typing import Any, Callable

from .schema import ToolStubConfig


class Stub:
    """A callable that stands in for a real tool. Constructed by
    build_stub() from a ToolStubConfig + the tool's signature meta."""

    def __init__(self, mode: str, fn: Callable[..., Any]):
        self.mode = mode
        self.fn = fn

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)


def build_stub(
    tool_name: str,
    tool_meta: dict,
    config: ToolStubConfig,
) -> Stub:
    """Phase 2: return a Stub configured per `config.mode`:
      - "real": pass-through (auto-probe uses the actual tool, no stub layer)
      - "schema": generate a value that matches tool_meta["returns"] shape
      - "semantic": one LLM call to fabricate a plausible response
      - "user": either config.canned (return as-is) or import config.callable_path
    """
    raise NotImplementedError("Phase 2 — see auto_probe/__init__.py")
