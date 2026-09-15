"""Subprocess-side inspector.

Runs INSIDE a child Python process with the target repo on sys.path.
Imports ``entry_module``, walks agent objects duck-typed by their
attributes, and prints a JSON fragment to stdout.

Duck-type: object has a string ``name`` attr, and either ``tools`` or
``sub_agents`` iterable. No dependency on google-adk — works against any
framework whose agent objects expose these attributes at runtime.

Two entry shapes:

- ``python -m adk_parser._inspector pkg.pipeline``
  Imports ``pkg.pipeline`` and walks its module-level attrs.

- ``python -m adk_parser._inspector pkg.pipeline build_root``
  Imports the module, calls ``pkg.pipeline.build_root()`` with no args,
  and walks the returned object recursively (plus module-level attrs).

The walker follows ``.sub_agents``, ``.tools``, and every callback attr
on discovered agents, dedupes by object id, and emits edges for
uses_tool / wraps_agent / owns_subagent / hook. Anonymous inline agents
(no ``name`` attr) get a synthetic ``anon_<id>`` name.

Emitted JSON shape:
    {
        "nodes": [
            {"kind": "llm_agent", "name": "researcher"}
        ],
        "edges": [
            {"kind": "uses_tool", "source_name": "researcher", "target_name": "search"},
            {"kind": "owns_subagent", "source_name": "pipeline", "target_name": "writer"},
            {"kind": "hook", "source_name": "researcher", "target_name": "before_agent",
             "phase": "before_agent_callback"}
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

# Six ADK callback kwargs the static parser already knows about — mirror them
# here so the inspector emits parallel `hook` edges.
CALLBACK_ATTRS = (
    "before_agent_callback",
    "after_agent_callback",
    "before_model_callback",
    "after_model_callback",
    "before_tool_callback",
    "after_tool_callback",
)


def _looks_like_agent(obj: Any) -> bool:
    if isinstance(obj, type):
        return False
    name = getattr(obj, "name", None)
    if not isinstance(name, str):
        return False
    return hasattr(obj, "tools") or hasattr(obj, "sub_agents")


def _kind_of(obj: Any) -> str:
    return AGENT_KIND_HINTS.get(type(obj).__name__, "custom_agent")


def _agent_name(obj: Any) -> str:
    n = getattr(obj, "name", None)
    if isinstance(n, str) and n:
        return n
    return f"anon_{id(obj):x}"


def _ref_name(obj: Any) -> str | None:
    """Best-effort human name for a tool, callback, or sub-agent reference."""
    if obj is None:
        return None
    # AgentTool-style: exposes `.agent`.
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


def _is_agent_ref(obj: Any) -> bool:
    """Is the item inside `tools=[...]` an AgentTool wrapping an agent?"""
    inner = getattr(obj, "agent", None)
    return inner is not None and _looks_like_agent(inner)


def _walk(
    obj: Any,
    nodes: list[dict],
    edges: list[dict],
    seen_ids: set[int],
) -> None:
    """Recursively descend an agent's sub_agents / tools / callbacks.

    Dedupes by ``id()`` so a shared child agent gets one node with fan-in
    edges instead of being emitted per parent.
    """
    if id(obj) in seen_ids:
        return
    if not _looks_like_agent(obj):
        return
    seen_ids.add(id(obj))

    agent_name = _agent_name(obj)
    nodes.append({"kind": _kind_of(obj), "name": agent_name})

    for t in getattr(obj, "tools", None) or []:
        ref = _ref_name(t)
        if not ref:
            continue
        if _is_agent_ref(t):
            edges.append(
                {"kind": "wraps_agent", "source_name": agent_name, "target_name": ref}
            )
            # Recurse into the wrapped agent so its sub-graph shows up too.
            _walk(getattr(t, "agent"), nodes, edges, seen_ids)
        else:
            edges.append(
                {"kind": "uses_tool", "source_name": agent_name, "target_name": ref}
            )

    for sa in getattr(obj, "sub_agents", None) or []:
        ref = _ref_name(sa)
        if ref:
            edges.append(
                {"kind": "owns_subagent", "source_name": agent_name, "target_name": ref}
            )
        _walk(sa, nodes, edges, seen_ids)

    for phase in CALLBACK_ATTRS:
        cb = getattr(obj, phase, None)
        if cb is None:
            continue
        # Some frameworks accept a list of callbacks per phase.
        for cb_one in cb if isinstance(cb, (list, tuple)) else [cb]:
            ref = _ref_name(cb_one)
            if ref:
                edges.append(
                    {
                        "kind": "hook",
                        "source_name": agent_name,
                        "target_name": ref,
                        "phase": phase,
                    }
                )


def inspect(entry_module: str, entry_object: str | None = None) -> dict:
    mod = importlib.import_module(entry_module)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[int] = set()

    # 1) If the caller named a specific object/callable, use it as the root.
    if entry_object:
        target = getattr(mod, entry_object, None)
        if target is None:
            return {
                "nodes": [],
                "edges": [],
                "errors": [f"entry_object '{entry_object}' not found in {entry_module}"],
            }
        if callable(target) and not _looks_like_agent(target):
            try:
                target = target()
            except Exception as e:
                return {
                    "nodes": [],
                    "edges": [],
                    "errors": [f"calling {entry_object}() raised {type(e).__name__}: {e}"],
                }
        _walk(target, nodes, edges, seen_ids)

    # 2) Always also sweep module-level attrs for agent objects the caller
    #    didn't name — cheap and catches the common "root = LlmAgent(...)"
    #    pattern even when entry_object was given.
    for _local_name, obj in list(vars(mod).items()):
        if _looks_like_agent(obj):
            _walk(obj, nodes, edges, seen_ids)

    return {"nodes": nodes, "edges": edges, "errors": []}


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"nodes": [], "edges": [], "errors": ["missing entry_module"]}))
        return 2
    entry = sys.argv[1]
    entry_object = sys.argv[2] if len(sys.argv) >= 3 else None
    try:
        payload = inspect(entry, entry_object)
    except Exception as e:
        payload = {"nodes": [], "edges": [], "errors": [f"{type(e).__name__}: {e}"]}
    json.dump(payload, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
