"""Subprocess-side inspector.

Runs INSIDE a child Python process with the target repo on sys.path.
Imports `entry_module`, walks module-level objects duck-typed as agents,
and prints a JSON fragment to stdout.

Duck-type: object has a string `name` attr, and either `tools` or
`sub_agents` iterable. No dependency on google-adk — works against any
framework whose agent objects expose these attributes at runtime.

Emitted JSON shape:
    {
        "nodes": [
            {"kind": "llm_agent", "name": "researcher"}
        ],
        "edges": [
            {"kind": "uses_tool", "source_name": "researcher", "target_name": "search"},
            {"kind": "owns_subagent", "source_name": "pipeline", "target_name": "writer"}
        ],
        "errors": []
    }
"""
from __future__ import annotations

import importlib
import json
import sys
from typing import Any


AGENT_KIND_HINTS = {
    "LlmAgent": "llm_agent",
    "Agent": "llm_agent",
    "SequentialAgent": "sequential_agent",
    "ParallelAgent": "parallel_agent",
    "LoopAgent": "loop_agent",
}


def _looks_like_agent(obj: Any) -> bool:
    if isinstance(obj, type):
        return False
    name = getattr(obj, "name", None)
    if not isinstance(name, str):
        return False
    return hasattr(obj, "tools") or hasattr(obj, "sub_agents")


def _kind_of(obj: Any) -> str:
    return AGENT_KIND_HINTS.get(type(obj).__name__, "custom_agent")


def _ref_name(obj: Any) -> str | None:
    """Best-effort human name for a tool or sub-agent reference."""
    if obj is None:
        return None
    # Wrapped agent: AgentTool-style objects expose `.agent`.
    inner = getattr(obj, "agent", None)
    if inner is not None:
        n = getattr(inner, "name", None)
        if isinstance(n, str):
            return n
    n = getattr(obj, "name", None)
    if isinstance(n, str):
        return n
    if callable(obj):
        return getattr(obj, "__name__", None) or getattr(obj, "__qualname__", None)
    return None


def inspect(entry_module: str) -> dict:
    mod = importlib.import_module(entry_module)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_agents: set[str] = set()

    for _local_name, obj in list(vars(mod).items()):
        if not _looks_like_agent(obj):
            continue
        agent_name = getattr(obj, "name")
        if agent_name in seen_agents:
            continue
        seen_agents.add(agent_name)
        nodes.append({"kind": _kind_of(obj), "name": agent_name})

        for t in getattr(obj, "tools", None) or []:
            ref = _ref_name(t)
            if ref:
                edges.append(
                    {"kind": "uses_tool", "source_name": agent_name, "target_name": ref}
                )
        for sa in getattr(obj, "sub_agents", None) or []:
            ref = _ref_name(sa)
            if ref:
                edges.append(
                    {"kind": "owns_subagent", "source_name": agent_name, "target_name": ref}
                )
    return {"nodes": nodes, "edges": edges, "errors": []}


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"nodes": [], "edges": [], "errors": ["missing entry_module"]}))
        return 2
    entry = sys.argv[1]
    try:
        payload = inspect(entry)
    except Exception as e:
        payload = {"nodes": [], "edges": [], "errors": [f"{type(e).__name__}: {e}"]}
    json.dump(payload, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
