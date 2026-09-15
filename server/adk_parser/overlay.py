"""Diff a static graph against a trace to classify each edge.

Every static edge lands in one of three buckets:

- ``both`` — the edge exists in the parse *and* fires at runtime. Confirmed
  path; render prominently.
- ``static_only`` — the parser saw the edge but the trace never followed
  it. Dead code, guarded branch, or a shape the trace didn't cover yet.
- ``observed_only`` — the trace exercised an edge the parser didn't
  extract. Parser gap; new edges added to the graph tagged so users can
  see where their static picture is under-approximating reality.
"""

from __future__ import annotations

from .schema import Edge, Graph, Node, Provenance
from .trace import ObservedEdge, ObservedNode, Trace, observed_from_spans


# All static agent kinds collapse to "agent" when matched against a trace,
# since a trace has no way to distinguish an LlmAgent from a SequentialAgent
# from the outside.
_STATIC_AGENT_KINDS = {
    "llm_agent",
    "sequential_agent",
    "parallel_agent",
    "loop_agent",
    "custom_agent",
}


def _match_kind(static_kind: str) -> str | None:
    if static_kind in _STATIC_AGENT_KINDS:
        return "agent"
    if static_kind in ("tool_function", "tool_builtin", "tool_mcp", "agent_as_tool"):
        return "tool"
    if static_kind == "callback":
        return "callback"
    return None


def _static_edge_key(edge: Edge, nodes_by_id: dict[str, Node]) -> ObservedEdge | None:
    src = nodes_by_id.get(edge.source)
    tgt = nodes_by_id.get(edge.target)
    if src is None or tgt is None:
        return None
    sk = _match_kind(src.kind)
    tk = _match_kind(tgt.kind)
    if sk is None or tk is None:
        return None
    return (sk, src.name, tk, tgt.name, edge.kind)


def classify(static_graph: Graph, trace: Trace) -> Graph:
    """Return a new ``Graph`` whose edges carry ``meta.status`` and whose
    nodes carry ``meta.observed`` where the trace confirmed them.

    Observed-only nodes are added as ``trace:<name>`` and edges as
    ``trace:<src>-><tgt>:<kind>`` with ``meta.runtime_only = True``.
    """
    obs_nodes, obs_edges = observed_from_spans(trace)

    # Deep copy via model round-trip so we don't mutate the input.
    graph = Graph.model_validate(static_graph.model_dump())

    nodes_by_id = {n.id: n for n in graph.nodes}
    observed_names_by_kind: dict[str, set[str]] = {"agent": set(), "tool": set(), "callback": set()}
    for kind, name in obs_nodes:
        observed_names_by_kind.setdefault(kind, set()).add(name)

    # Tag nodes we saw.
    matched_names: dict[str, set[str]] = {"agent": set(), "tool": set(), "callback": set()}
    for node in graph.nodes:
        mk = _match_kind(node.kind)
        if mk is None:
            continue
        if node.name in observed_names_by_kind.get(mk, set()):
            node.meta["observed"] = True
            matched_names.setdefault(mk, set()).add(node.name)

    # Add trace-only nodes.
    for kind, name in obs_nodes:
        if name in matched_names.get(kind, set()):
            continue
        trace_id = f"trace:{kind}:{name}"
        if any(n.id == trace_id for n in graph.nodes):
            continue
        graph.nodes.append(
            Node(
                id=trace_id,
                # Fall back to a nearby static kind so the client's typed nodes
                # still pick a template. Agents default to llm_agent, tools to
                # tool_function.
                kind={"agent": "llm_agent", "tool": "tool_function", "callback": "callback"}[kind],
                name=name,
                provenance=None,
                meta={"runtime_only": True, "observed": True, "trace_kind": kind},
            )
        )
        nodes_by_id[trace_id] = graph.nodes[-1]

    # Index observed edges for fast lookup.
    obs_edge_set = set(obs_edges)

    # Tag static edges + collect the ones the trace also saw.
    matched_obs: set[ObservedEdge] = set()
    for edge in graph.edges:
        key = _static_edge_key(edge, nodes_by_id)
        if key is None:
            edge.meta["status"] = "unknown"
            continue
        if key in obs_edge_set:
            edge.meta["status"] = "both"
            matched_obs.add(key)
        else:
            edge.meta["status"] = "static_only"

    # Observed-only edges get added.
    def _resolve_endpoint(kind: str, name: str) -> str | None:
        # Match by name against tagged nodes first; fall back to trace-only.
        for node in graph.nodes:
            mk = _match_kind(node.kind)
            if mk == kind and node.name == name:
                return node.id
        return None

    for key in obs_edges - matched_obs:
        sk, sname, tk, tname, ekind = key
        s_id = _resolve_endpoint(sk, sname)
        t_id = _resolve_endpoint(tk, tname)
        if s_id is None or t_id is None:
            continue
        eid = f"trace:{s_id}->{t_id}:{ekind}"
        if any(e.id == eid for e in graph.edges):
            continue
        graph.edges.append(
            Edge(
                id=eid,
                source=s_id,
                target=t_id,
                kind=ekind,
                meta={"status": "observed_only", "runtime_only": True},
            )
        )

    return graph
