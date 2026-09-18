"""Runs one query against a target ADK agent and captures its trace.

Implementation lands in Phase 1. This file exists so Phase 0 can wire the
HTTP endpoint and downstream modules can import the interface.
"""
from __future__ import annotations

from .schema import InvokeRequest


class NotImplementedYet(RuntimeError):
    """Explicit marker so endpoints return 501 with a clear message."""


def invoke_once(req: InvokeRequest) -> dict:
    """Run a single query in a session, return {trace, session_id, state}.

    Phase 1 will implement:
      1. Spawn subprocess with `repo_path` on sys.path.
      2. Import `entry_module`; resolve `entry_object` if given.
      3. Instantiate an ADK Runner around the root agent.
      4. Monkey-patch every discovered agent's six callback attrs to the
         Tracer wrappers so we get spans.
      5. Apply stub-mode wrappers on tool functions per req.tool_stubs.
      6. Call runner.run(session_id, query); collect spans.
      7. Serialize + return.
    """
    raise NotImplementedYet(
        "auto_probe.invoker.invoke_once is a Phase 1 deliverable — see "
        "ROADMAP.md / auto_probe/__init__.py for the plan."
    )
