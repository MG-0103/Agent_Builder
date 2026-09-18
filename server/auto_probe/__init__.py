"""Auto-probe: exercises an ADK agent workflow with LLM-generated queries
and reports which static graph edges actually fire.

Depends on `adk_parser` for the static graph, `adk_parser.tracer` for span
emission, and `adk_parser.probe` machinery for subprocess isolation. Nothing
in `adk_parser` imports from here — the dependency is one-way.

Phase 0: scaffolding only. Endpoints return 501 until each phase lands.
Phase 1 wires the invoker. Phase 2 adds stub-mode. Phase 3 adds the query
generator. Phase 4 adds multi-turn sessions. Phase 5 wires the orchestrator.
"""

__all__ = ["invoker", "stubs", "generator", "session", "orchestrator", "endpoints"]
