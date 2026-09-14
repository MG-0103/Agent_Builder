from pathlib import Path

from adk_parser import Graph, run_probe, merge_runtime

FIXTURE = Path(__file__).parent / "fixtures" / "runtime_probe"


def test_probe_discovers_agents():
    observed = run_probe(FIXTURE, "agent")
    names = {n["name"] for n in observed["nodes"]}
    assert {"researcher", "writer", "pipeline"} <= names
    assert observed["errors"] == []


def test_probe_discovers_tool_edges():
    observed = run_probe(FIXTURE, "agent")
    tool_edges = [e for e in observed["edges"] if e["kind"] == "uses_tool"]
    tools_of_researcher = {e["target_name"] for e in tool_edges if e["source_name"] == "researcher"}
    assert tools_of_researcher == {"search", "summarize"}


def test_probe_discovers_sub_agents():
    observed = run_probe(FIXTURE, "agent")
    sub_edges = [e for e in observed["edges"] if e["kind"] == "owns_subagent"]
    subs = {(e["source_name"], e["target_name"]) for e in sub_edges}
    assert ("pipeline", "researcher") in subs
    assert ("pipeline", "writer") in subs


def test_merge_marks_static_nodes_observed():
    g = Graph(source_root=str(FIXTURE))
    from adk_parser.schema import Node
    g.nodes.append(Node(id="s:agent:researcher", kind="llm_agent", name="researcher"))
    observed = {"nodes": [{"kind": "llm_agent", "name": "researcher"}], "edges": [], "errors": []}
    merged = merge_runtime(g, observed)
    n = next(x for x in merged.nodes if x.name == "researcher")
    assert n.meta.get("observed") is True


def test_merge_adds_runtime_only_agent():
    g = Graph(source_root=str(FIXTURE))
    observed = {"nodes": [{"kind": "llm_agent", "name": "ghost"}], "edges": [], "errors": []}
    merged = merge_runtime(g, observed)
    ghost = next(x for x in merged.nodes if x.name == "ghost")
    assert ghost.id == "runtime:ghost"
    assert ghost.meta.get("runtime_only") is True


def test_merge_full_probe_flow():
    """Simulate the full flow: empty static graph + real probe run."""
    g = Graph(source_root=str(FIXTURE))
    observed = run_probe(FIXTURE, "agent")
    merged = merge_runtime(g, observed)
    names = {n.name for n in merged.nodes}
    assert {"researcher", "writer", "pipeline", "search", "summarize"} <= names
    # All discovered nodes should be tagged observed.
    for n in merged.nodes:
        assert n.meta.get("observed") is True
