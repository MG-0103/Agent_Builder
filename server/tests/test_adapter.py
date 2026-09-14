from pathlib import Path

from adk_parser import parse_path

FIXTURE = Path(__file__).parent / "fixtures" / "simple_agent"
MULTI = Path(__file__).parent / "fixtures" / "multi_file"
REEXPORT = Path(__file__).parent / "fixtures" / "reexport"
ALIAS = Path(__file__).parent / "fixtures" / "alias_import"
ROOT_ABS = Path(__file__).parent / "fixtures" / "root_absolute"
CYCLE = Path(__file__).parent / "fixtures" / "import_cycle"
SHARED_CB = Path(__file__).parent / "fixtures" / "shared_callback"
MALFORMED = Path(__file__).parent / "fixtures" / "malformed"
GRAPH_API = Path(__file__).parent / "fixtures" / "graph_api"
CUSTOM = Path(__file__).parent / "fixtures" / "custom_agent"
CUSTOM_CROSS = Path(__file__).parent / "fixtures" / "custom_cross"
ATTR_CHAIN = Path(__file__).parent / "fixtures" / "attr_chain"


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


def test_reexport_chain_resolves():
    g = parse_path(REEXPORT)
    pipeline = _find(_by_kind(g, "sequential_agent"), "pipeline")
    researcher = _find(_by_kind(g, "llm_agent"), "researcher")
    owns = [e for e in g.edges if e.kind == "owns_subagent" and e.source == pipeline.id]
    assert len(owns) == 1
    assert owns[0].target == researcher.id
    assert g.unresolved == []


def test_import_alias_is_recognized():
    g = parse_path(ALIAS)
    names = {n.name for n in _by_kind(g, "llm_agent")}
    assert names == {"alpha", "beta"}
    assert len(_by_kind(g, "sequential_agent")) == 1
    pipeline = _find(_by_kind(g, "sequential_agent"), "pipeline")
    owns = [e for e in g.edges if e.kind == "owns_subagent" and e.source == pipeline.id]
    assert len(owns) == 2
    assert g.unresolved == []


def test_root_absolute_import_no_package():
    g = parse_path(ROOT_ABS)
    assert len(_by_kind(g, "llm_agent")) == 1
    assert _by_kind(g, "llm_agent")[0].name == "solo"


def test_cycle_does_not_hang_and_marks_unresolved():
    g = parse_path(CYCLE)
    agent = _find(_by_kind(g, "llm_agent"), "cyc")
    owns = [e for e in g.edges if e.kind == "owns_subagent" and e.source == agent.id]
    assert len(owns) == 1
    # Symbol `thing` cycles a<->b and is never bound; must land in unresolved.
    assert any(u.get("symbol") == "thing" for u in g.unresolved)


def test_shared_callback_deduped():
    g = parse_path(SHARED_CB)
    cbs = _by_kind(g, "callback")
    assert len(cbs) == 1
    hooks = [e for e in g.edges if e.kind == "hook"]
    assert len(hooks) == 2
    assert {h.target for h in hooks} == {cbs[0].id}


def test_malformed_file_skipped_good_still_parsed():
    g = parse_path(MALFORMED)
    names = {n.name for n in _by_kind(g, "llm_agent")}
    assert names == {"good"}


def test_graph_api_linear_edge():
    g = parse_path(GRAPH_API)
    planner = _find(_by_kind(g, "llm_agent"), "planner")
    approver = _find(_by_kind(g, "llm_agent"), "approver")
    edges = [e for e in g.edges if e.kind == "graph_edge"]
    assert any(e.source == planner.id and e.target == approver.id for e in edges)


def test_graph_api_conditional_edges():
    g = parse_path(GRAPH_API)
    approver = _find(_by_kind(g, "llm_agent"), "approver")
    publisher = _find(_by_kind(g, "llm_agent"), "publisher")
    rejector = _find(_by_kind(g, "llm_agent"), "rejector")
    cond = [e for e in g.edges if e.kind == "graph_edge" and e.source == approver.id and e.meta.get("case")]
    targets = {e.target: e.meta.get("case") for e in cond}
    assert targets[publisher.id] == "approved"
    assert targets[rejector.id] == "rejected"
    assert all(e.meta.get("router") == "route" for e in cond)


def test_graph_api_entry_point():
    g = parse_path(GRAPH_API)
    planner = _find(_by_kind(g, "llm_agent"), "planner")
    assert planner.meta.get("entry_point") is True


def test_custom_agent_direct_llm_subclass():
    g = parse_path(CUSTOM)
    r = _find(g.nodes, "r")
    assert r.kind == "llm_agent"
    assert r.meta["class"] == "Reviewer"


def test_custom_agent_transitive_subclass():
    g = parse_path(CUSTOM)
    d = _find(g.nodes, "d")
    assert d.kind == "llm_agent"
    assert d.meta["class"] == "DeepReviewer"


def test_custom_agent_base_agent_subclass():
    g = parse_path(CUSTOM)
    c = _find(g.nodes, "c")
    assert c.kind == "custom_agent"
    assert c.meta["class"] == "MyThing"


def test_custom_agent_cross_file_direct():
    g = parse_path(CUSTOM_CROSS)
    r = _find(g.nodes, "r")
    assert r.kind == "llm_agent"
    assert r.meta["class"] == "Reviewer"


def test_custom_agent_cross_file_transitive():
    g = parse_path(CUSTOM_CROSS)
    d = _find(g.nodes, "d")
    assert d.kind == "llm_agent"
    assert d.meta["class"] == "DeepReviewer"


def test_attr_chain_sub_agent_import_module():
    g = parse_path(ATTR_CHAIN)
    pipeline = _find(_by_kind(g, "sequential_agent"), "pipeline")
    researcher = _find(_by_kind(g, "llm_agent"), "researcher")
    owns = [e for e in g.edges if e.kind == "owns_subagent" and e.source == pipeline.id]
    assert researcher.id in {e.target for e in owns}


def test_attr_chain_tool_via_module_alias():
    g = parse_path(ATTR_CHAIN)
    tools = [n for n in _by_kind(g, "tool_function") if n.name == "search_web"]
    assert len(tools) == 1
    assert tools[0].meta.get("defined_in") == "pkg.tools_mod"


def test_attr_chain_no_unresolved():
    g = parse_path(ATTR_CHAIN)
    assert g.unresolved == []
