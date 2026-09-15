"""Round-trip parity: parse → emit → parse produces the same graph.

Excludes fixtures the emitter can't reproduce (custom subclasses, MCP
toolsets, unresolved dynamic tools) — those are correct EmitSkipped
cases, not bugs. See ``codegen.py`` docstring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adk_parser import parse_path
from adk_parser.codegen import EmitSkipped, emit_python

FIXTURES = Path(__file__).parent / "fixtures"

# Fixtures with only round-trippable node kinds.
ROUND_TRIP_FIXTURES = [
    "simple_agent",
    "multi_file",
    "reexport",
    "alias_import",
    "root_absolute",
    "attr_chain",
    "state_flow",
    "graph_api",
    "shared_callback",
]


def _normalize(graph):
    """Reduce a graph to a structural signature.

    Drops node ids (they encode fq_module + line), provenance, and line-
    bearing meta (dynamic tool line numbers). Keeps kind, name, meta keys
    that affect semantics, plus edge kind + endpoint *names* rather than
    ids.
    """
    id_to_name: dict[str, tuple[str, str]] = {
        n.id: (n.kind, n.name) for n in graph.nodes
    }

    meta_keys_for_kind = {
        "llm_agent": {"model", "output_key", "instruction"},
        "sequential_agent": set(),
        "parallel_agent": set(),
        "loop_agent": set(),
        "tool_function": set(),
        "callback": set(),
        "agent_as_tool": set(),
    }

    nodes = []
    for n in graph.nodes:
        keep = meta_keys_for_kind.get(n.kind, set())
        meta = {k: v for k, v in (n.meta or {}).items() if k in keep}
        nodes.append((n.kind, n.name, tuple(sorted(meta.items()))))
    nodes.sort()

    edges = []
    for e in graph.edges:
        s = id_to_name.get(e.source)
        t = id_to_name.get(e.target)
        if s is None or t is None:
            continue
        # graph_edge / shares_state meta may carry case/router/key; keep case
        # and key because they change routing semantics; drop router (it's a
        # function reference and its identity varies across emits).
        meta = e.meta or {}
        keep = {}
        if "case" in meta:
            keep["case"] = meta["case"]
        if "key" in meta:
            keep["key"] = meta["key"]
        if "phase" in meta:
            keep["phase"] = meta["phase"]
        edges.append((e.kind, s, t, tuple(sorted(keep.items()))))
    edges.sort()

    return {"nodes": nodes, "edges": edges}


@pytest.mark.parametrize("fixture", ROUND_TRIP_FIXTURES)
def test_round_trip(fixture, tmp_path):
    src = FIXTURES / fixture
    g1 = parse_path(src)
    py = emit_python(g1)

    (tmp_path / "emitted.py").write_text(py)
    g2 = parse_path(tmp_path)

    n1 = _normalize(g1)
    n2 = _normalize(g2)

    assert n1["nodes"] == n2["nodes"], (
        f"nodes differ for {fixture}:\n"
        f"emitted source:\n{py}\n"
    )
    assert n1["edges"] == n2["edges"], (
        f"edges differ for {fixture}:\n"
        f"emitted source:\n{py}\n"
    )


def test_custom_agent_skipped():
    """Custom subclasses aren't round-trippable — the emitter must refuse."""
    g = parse_path(FIXTURES / "custom_agent")
    with pytest.raises(EmitSkipped):
        emit_python(g)


def test_dynamic_tools_skipped():
    g = parse_path(FIXTURES / "dynamic_tools")
    with pytest.raises(EmitSkipped):
        emit_python(g)


def test_emit_is_deterministic():
    """Same graph in → same source out; guards codegen against dict-order
    surprises."""
    g = parse_path(FIXTURES / "simple_agent")
    assert emit_python(g) == emit_python(g)
