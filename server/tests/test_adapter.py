from pathlib import Path

from adk_parser import parse_path

FIXTURE = Path(__file__).parent / "fixtures" / "simple_agent"
MULTI = Path(__file__).parent / "fixtures" / "multi_file"


def _by_kind(graph, kind):
    return [n for n in graph.nodes if n.kind == kind]


def test_extracts_agents():
    g = parse_path(FIXTURE)
    names = {n.name for n in _by_kind(g, "llm_agent")}
    assert {"researcher", "writer"} <= names


def test_extracts_sequential_agent():
    g = parse_path(FIXTURE)
    seq = _by_kind(g, "sequential_agent")
    assert len(seq) == 1
    assert seq[0].name == "pipeline"


def test_extracts_tools():
    g = parse_path(FIXTURE)
    tool_names = {n.name for n in _by_kind(g, "tool_function")}
    assert {"search_web", "summarize"} <= tool_names


def test_extracts_agent_as_tool():
    g = parse_path(FIXTURE)
    aat = _by_kind(g, "agent_as_tool")
    assert len(aat) == 1
    # After resolver: wraps == real researcher node id (same file case).
    researcher = next(n for n in _by_kind(g, "llm_agent") if n.name == "researcher")
    assert aat[0].meta["wraps"] == researcher.id


def _find(nodes, name):
    return next(n for n in nodes if n.name == name)


def test_multi_file_resolves_sub_agents():
    g = parse_path(MULTI)
    pipeline = _find(_by_kind(g, "sequential_agent"), "pipeline")
    researcher = _find(_by_kind(g, "llm_agent"), "researcher")
    writer = _find(_by_kind(g, "llm_agent"), "writer")

    owns = [e for e in g.edges if e.kind == "owns_subagent" and e.source == pipeline.id]
    targets = {e.target for e in owns}
    assert researcher.id in targets
    assert writer.id in targets


def test_multi_file_resolves_agent_as_tool_across_files():
    g = parse_path(MULTI)
    aat = _by_kind(g, "agent_as_tool")
    researcher = _find(_by_kind(g, "llm_agent"), "researcher")
    assert len(aat) == 1
    assert aat[0].meta["wraps"] == researcher.id


def test_multi_file_no_unresolved():
    g = parse_path(MULTI)
    assert g.unresolved == []


def test_extracts_callback():
    g = parse_path(FIXTURE)
    cbs = _by_kind(g, "callback")
    assert any(c.name == "before_agent" for c in cbs)
    assert any(e.kind == "hook" for e in g.edges)


def test_extracts_subagent_edges():
    g = parse_path(FIXTURE)
    owns = [e for e in g.edges if e.kind == "owns_subagent"]
    assert len(owns) == 2
