"""Trace overlay: classify(static, trace) tags each edge with status."""

from __future__ import annotations

from pathlib import Path

from adk_parser import Span, Trace, classify, parse_path
from adk_parser.tracer import Tracer

FIXTURES = Path(__file__).parent / "fixtures"


def _edge_between(graph, src_name, tgt_name):
    by_id = {n.id: n for n in graph.nodes}
    for e in graph.edges:
        s = by_id.get(e.source)
        t = by_id.get(e.target)
        if s and t and s.name == src_name and t.name == tgt_name:
            return e
    return None


def test_static_only_when_no_trace():
    g = parse_path(FIXTURES / "simple_agent")
    merged = classify(g, Trace(spans=[]))
    for e in merged.edges:
        assert e.meta.get("status") == "static_only"


def test_confirms_edges_when_trace_covers_them():
    g = parse_path(FIXTURES / "simple_agent")

    # Hand-built trace: pipeline invokes researcher (which calls search_web)
    # and writer. Missing: writer's AgentTool(researcher), so the wraps_agent
    # edge should stay static_only.
    spans = [
        Span(id="a1", kind="agent", name="pipeline"),
        Span(id="a2", kind="agent", name="researcher", parent_id="a1"),
        Span(id="t1", kind="tool_call", name="search_web", parent_id="a2"),
        Span(id="c1", kind="callback", name="before_agent", parent_id="a2"),
        Span(id="a3", kind="agent", name="writer", parent_id="a1"),
    ]

    merged = classify(g, Trace(spans=spans))

    pipe_to_researcher = _edge_between(merged, "pipeline", "researcher")
    assert pipe_to_researcher is not None
    assert pipe_to_researcher.meta["status"] == "both"

    pipe_to_writer = _edge_between(merged, "pipeline", "writer")
    assert pipe_to_writer is not None
    assert pipe_to_writer.meta["status"] == "both"

    researcher_to_search = _edge_between(merged, "researcher", "search_web")
    assert researcher_to_search is not None
    assert researcher_to_search.meta["status"] == "both"

    researcher_to_cb = _edge_between(merged, "researcher", "before_agent")
    assert researcher_to_cb is not None
    assert researcher_to_cb.meta["status"] == "both"

    # writer → AgentTool(researcher) never ran → static_only.
    # AgentTool node's name is 'researcher' (the wrapped agent). Look for a
    # wraps_agent-kind edge from writer.
    wraps = [e for e in merged.edges if e.kind == "wraps_agent"]
    assert wraps, "expected a wraps_agent edge in the static graph"
    for e in wraps:
        assert e.meta["status"] == "static_only"


def test_observed_only_when_trace_shows_edge_parser_missed():
    g = parse_path(FIXTURES / "simple_agent")

    # Trace says researcher uses a tool the parser didn't extract.
    spans = [
        Span(id="a1", kind="agent", name="researcher"),
        Span(id="t1", kind="tool_call", name="mystery_tool", parent_id="a1"),
    ]
    merged = classify(g, Trace(spans=spans))

    # Trace-only node was added.
    mystery = [n for n in merged.nodes if n.name == "mystery_tool"]
    assert mystery, "expected a runtime-only node for mystery_tool"
    assert mystery[0].meta.get("runtime_only") is True

    # And a trace-only edge with observed_only status.
    e = _edge_between(merged, "researcher", "mystery_tool")
    assert e is not None
    assert e.meta["status"] == "observed_only"
    assert e.meta.get("runtime_only") is True


def test_tracer_produces_valid_spans():
    """Tracer wrappers emit spans with correct parent linkage."""
    tracer = Tracer()

    outer = tracer.wrap_agent_callback("outer")
    tool = tracer.wrap_tool_callback("outer")

    outer()

    # Nested: inside a running agent, tools should link as children.
    def _inner_body():
        tool(None, "search_web")

    tracer.wrap_agent_callback("nested", inner=_inner_body)()

    trace = tracer.trace()
    kinds = [s.kind for s in trace.spans]
    assert "agent" in kinds
    assert "tool_call" in kinds

    # Every tool_call span has an agent parent.
    by_id = {s.id: s for s in trace.spans}
    for s in trace.spans:
        if s.kind == "tool_call":
            assert s.parent_id is not None
            assert by_id[s.parent_id].kind == "agent"
