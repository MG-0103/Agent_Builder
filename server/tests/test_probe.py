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


def test_probe_error_becomes_graph_warning():
    """A missing entry module surfaces as a probe_error warning after merge."""
    g = Graph(source_root=str(FIXTURE))
    observed = run_probe(FIXTURE, "does_not_exist_module")
    assert observed["errors"], "expected import failure to be captured"
    merged = merge_runtime(g, observed)
    kinds = {w.get("kind") for w in merged.warnings}
    assert "probe_error" in kinds
    # Each error string becomes one warning message.
    msgs = [w.get("message") for w in merged.warnings if w.get("kind") == "probe_error"]
    assert all(isinstance(m, str) for m in msgs)


FACTORY = Path(__file__).parent / "fixtures" / "factory_probe"


def test_entry_object_walks_factory_return():
    observed = run_probe(FACTORY, "agent", entry_object="build_root")
    names = {n["name"] for n in observed["nodes"]}
    assert {"researcher", "writer", "pipeline"} <= names
    # Sub-agent edges from the pipeline should surface.
    subs = {
        (e["source_name"], e["target_name"])
        for e in observed["edges"]
        if e["kind"] == "owns_subagent"
    }
    assert ("pipeline", "researcher") in subs
    assert ("pipeline", "writer") in subs
    # Tool edges from the deeper walker.
    tool_targets = {
        e["target_name"] for e in observed["edges"]
        if e["kind"] == "uses_tool" and e["source_name"] == "researcher"
    }
    assert {"_search", "_summarize"} <= tool_targets
    # Callback hook edge with phase.
    hooks = [e for e in observed["edges"] if e["kind"] == "hook"]
    assert any(e["source_name"] == "researcher" and e.get("phase") == "before_agent_callback"
               for e in hooks)


def test_deeper_walker_dedupes_shared_child():
    """A shared sub-agent should appear once, with two fan-in owns_subagent
    edges."""
    import textwrap
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as td:
        p = Path(td) / "agent.py"
        p.write_text(textwrap.dedent("""
            class _A:
                def __init__(self, name, sub_agents=None):
                    self.name = name
                    self.sub_agents = sub_agents or []
                    self.tools = []
            shared = _A(name="shared")
            parent_a = _A(name="parent_a", sub_agents=[shared])
            parent_b = _A(name="parent_b", sub_agents=[shared])
        """))
        observed = run_probe(td, "agent")
        shared_nodes = [n for n in observed["nodes"] if n["name"] == "shared"]
        assert len(shared_nodes) == 1
        parents_of_shared = {
            e["source_name"] for e in observed["edges"]
            if e["kind"] == "owns_subagent" and e["target_name"] == "shared"
        }
        assert parents_of_shared == {"parent_a", "parent_b"}


def test_entry_object_missing_returns_error():
    observed = run_probe(FACTORY, "agent", entry_object="not_a_thing")
    assert observed["errors"]
    assert "not_a_thing" in observed["errors"][0]
