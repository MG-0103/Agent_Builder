"""Graph → ADK Python source emitter.

Flat single-file emit: one Python module reproducing the workflow that the
static extractor read out of a repo. Preserving original file layout is a
future step; the goal here is to prove the graph fully captures the
semantics, via a parse → emit → parse round-trip.

Non-round-trippable node kinds (raise `EmitSkipped` when hit):
- ``custom_agent``: the user's subclass isn't importable from ADK.
- ``tool_mcp``: external toolset with runtime-only shape.
- tool_function nodes marked ``meta.dynamic`` or named ``<unresolved>``.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .schema import Edge, Graph, Node


class EmitSkipped(Exception):
    """Raised when the graph contains a node kind the emitter can't reproduce."""


# ADK class per node kind.
_AGENT_CLASS = {
    "llm_agent": "LlmAgent",
    "sequential_agent": "SequentialAgent",
    "parallel_agent": "ParallelAgent",
    "loop_agent": "LoopAgent",
}


def _by_id(nodes: Iterable[Node]) -> dict[str, Node]:
    return {n.id: n for n in nodes}


def _topo_agents(agent_ids: list[str], edges: list[Edge]) -> list[str]:
    """Return agents ordered so every sub-agent precedes its parent.

    Children before parents so `sub_agents=[child_a, child_b]` refers to
    already-bound names when the parent is emitted.
    """
    children: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = {a: 0 for a in agent_ids}
    agent_set = set(agent_ids)
    for e in edges:
        if e.kind != "owns_subagent":
            continue
        if e.source in agent_set and e.target in agent_set:
            children[e.source].append(e.target)

    # Kahn from leaves. A leaf here = an agent nobody else lists as a sub.
    parents: dict[str, int] = {a: 0 for a in agent_ids}
    for _, ch in children.items():
        for c in ch:
            parents[c] += 1

    order: list[str] = []
    ready = [a for a, p in parents.items() if p == 0]
    # Walk descendants first: reverse post-order of the sub-agent DAG.
    seen: set[str] = set()

    def visit(a: str) -> None:
        if a in seen:
            return
        seen.add(a)
        for c in children.get(a, []):
            visit(c)
        order.append(a)

    for root in ready:
        visit(root)
    # Any orphans still not seen (cycle or disconnected) get appended.
    for a in agent_ids:
        if a not in seen:
            visit(a)
    return order


def _py_str(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _local_name(node: Node, taken: dict[str, str]) -> str:
    """A Python-legal local variable for the node's display name."""
    if node.id in taken:
        return taken[node.id]
    base = "".join(c if c.isalnum() or c == "_" else "_" for c in node.name)
    if not base or base[0].isdigit():
        base = "_" + base
    name = base
    n = 2
    used = set(taken.values())
    while name in used:
        name = f"{base}_{n}"
        n += 1
    taken[node.id] = name
    return name


def _tools_for(agent_id: str, edges: list[Edge], nodes: dict[str, Node]) -> list[Edge]:
    return [
        e for e in edges
        if e.source == agent_id and e.kind in ("uses_tool", "wraps_agent")
        and e.target in nodes
    ]


def _subs_for(agent_id: str, edges: list[Edge], nodes: dict[str, Node]) -> list[Edge]:
    subs = [
        e for e in edges
        if e.source == agent_id and e.kind == "owns_subagent" and e.target in nodes
    ]
    subs.sort(key=lambda e: e.meta.get("order", 0) if isinstance(e.meta, dict) else 0)
    return subs


def _hooks_for(agent_id: str, edges: list[Edge], nodes: dict[str, Node]) -> list[Edge]:
    return [
        e for e in edges
        if e.source == agent_id and e.kind == "hook" and e.target in nodes
    ]


def _emit_tool_stubs(tool_nodes: list[Node]) -> list[str]:
    lines: list[str] = []
    for n in tool_nodes:
        if isinstance(n.meta, dict) and n.meta.get("dynamic"):
            raise EmitSkipped(f"tool marked dynamic/unresolved: {n.name}")
        lines.append(f"def {n.name}(*args, **kwargs):")
        lines.append("    return None")
        lines.append("")
    return lines


def _emit_callback_stubs(cb_nodes: list[Node]) -> list[str]:
    lines: list[str] = []
    for n in cb_nodes:
        lines.append(f"def {n.name}(*args, **kwargs):")
        lines.append("    return None")
        lines.append("")
    return lines


def _agent_call(
    node: Node,
    edges: list[Edge],
    nodes: dict[str, Node],
    local_of: dict[str, str],
) -> str:
    cls = _AGENT_CLASS.get(node.kind)
    if cls is None:
        raise EmitSkipped(f"non-emittable agent kind: {node.kind} ({node.name})")

    parts: list[str] = [f'name={_py_str(node.name)}']
    meta = node.meta if isinstance(node.meta, dict) else {}
    model = meta.get("model")
    if isinstance(model, str):
        parts.append(f"model={_py_str(model)}")
    instr = meta.get("instruction")
    if isinstance(instr, str):
        parts.append(f"instruction={_py_str(instr)}")
    output_key = meta.get("output_key")
    if isinstance(output_key, str):
        parts.append(f"output_key={_py_str(output_key)}")

    tool_edges = _tools_for(node.id, edges, nodes)
    if tool_edges:
        items: list[str] = []
        for e in tool_edges:
            target = nodes[e.target]
            if target.kind == "agent_as_tool":
                # `meta.wraps` is the resolved wrapped-agent id (see
                # adapter.py resolver); `wraps_ref` stays as the raw
                # placeholder for anything that could not resolve.
                wrapped_ref = target.meta.get("wraps") if isinstance(target.meta, dict) else None
                wrapped_local = local_of.get(wrapped_ref or "", None)
                if wrapped_local is None:
                    raise EmitSkipped(f"agent_as_tool references unknown agent: {target.name}")
                items.append(f"AgentTool(agent={wrapped_local})")
            elif target.kind == "tool_function":
                if isinstance(target.meta, dict) and target.meta.get("dynamic"):
                    raise EmitSkipped(f"dynamic tool ref in {node.name}")
                items.append(target.name)
            elif target.kind == "tool_mcp":
                raise EmitSkipped(f"MCP toolset in {node.name}")
            else:
                raise EmitSkipped(f"unhandled tool kind: {target.kind}")
        parts.append("tools=[" + ", ".join(items) + "]")

    sub_edges = _subs_for(node.id, edges, nodes)
    if sub_edges:
        names = [local_of[e.target] for e in sub_edges if e.target in local_of]
        parts.append("sub_agents=[" + ", ".join(names) + "]")

    for e in _hooks_for(node.id, edges, nodes):
        phase = e.meta.get("phase") if isinstance(e.meta, dict) else None
        cb = nodes[e.target].name
        if isinstance(phase, str):
            parts.append(f"{phase}={cb}")

    body = ",\n    ".join(parts)
    return f"{cls}(\n    {body},\n)"


def _graph_builder_blocks(graph: Graph, local_of: dict[str, str]) -> list[str]:
    """Emit `g.add_node/.add_edge/...` for each graph_edge cluster.

    Groups edges by ``meta.builder`` when set; otherwise emits one shared
    ``g`` builder covering all graph_edge rows. Good enough for round-trip
    parity given today's extractor.
    """
    graph_edges = [e for e in graph.edges if e.kind == "graph_edge"]
    if not graph_edges:
        return []

    lines: list[str] = ["", "g = Graph()"]
    # Discover agents involved in graph edges and register them as nodes.
    involved: list[str] = []
    for e in graph_edges:
        for endpoint in (e.source, e.target):
            if endpoint in local_of and endpoint not in involved:
                involved.append(endpoint)
    for a in involved:
        lines.append(f'g.add_node({_py_str(local_of[a])}, {local_of[a]})')

    # Conditional edges: group by (source, router).
    plain: list[Edge] = []
    cond: dict[tuple[str, str], list[Edge]] = defaultdict(list)
    for e in graph_edges:
        meta = e.meta if isinstance(e.meta, dict) else {}
        router = meta.get("router")
        if router:
            cond[(e.source, str(router))].append(e)
        else:
            plain.append(e)

    for e in plain:
        if e.source in local_of and e.target in local_of:
            lines.append(
                f'g.add_edge({_py_str(local_of[e.source])}, {_py_str(local_of[e.target])})'
            )

    for (src, router), group in cond.items():
        mapping_parts = []
        for e in group:
            case = e.meta.get("case") if isinstance(e.meta, dict) else None
            if case is None:
                continue
            mapping_parts.append(f"{_py_str(str(case))}: {_py_str(local_of[e.target])}")
        mapping = "{" + ", ".join(mapping_parts) + "}"
        lines.append(
            f'g.add_conditional_edges({_py_str(local_of[src])}, {router}, {mapping})'
        )
        # Router functions need to exist; emit a stub above the builder block.
        lines.insert(0, f"def {router}(*args, **kwargs):\n    return None\n")

    return lines


def emit_python(graph: Graph) -> str:
    """Return a single-file ADK Python source for ``graph``.

    Raises ``EmitSkipped`` if the graph contains a node the emitter can't
    reproduce (custom agent subclass, MCP toolset, unresolved tool).
    """
    nodes = _by_id(graph.nodes)

    # Bucket by node kind for emit order.
    agent_ids = [n.id for n in graph.nodes if n.kind in _AGENT_CLASS]
    custom_ids = [n.id for n in graph.nodes if n.kind == "custom_agent"]
    if custom_ids:
        raise EmitSkipped(f"custom_agent kinds present: {[nodes[i].name for i in custom_ids]}")

    for w in graph.warnings:
        if isinstance(w, dict) and w.get("kind") == "dynamic_tools":
            raise EmitSkipped("dynamic_tools warning; parser gave up on a tool list")

    tool_nodes = [n for n in graph.nodes if n.kind == "tool_function"]
    for t in tool_nodes:
        if t.name == "<unresolved>":
            raise EmitSkipped("unresolved tool present")
    cb_nodes = [n for n in graph.nodes if n.kind == "callback"]
    mcp = [n for n in graph.nodes if n.kind == "tool_mcp"]
    if mcp:
        raise EmitSkipped("tool_mcp present")

    # Local names in emit order.
    local_of: dict[str, str] = {}
    for n in tool_nodes:
        _local_name(n, local_of)
    for n in cb_nodes:
        _local_name(n, local_of)
    # Agents in topo order so parents can name their subs.
    ordered_agents = _topo_agents(agent_ids, graph.edges)
    for aid in ordered_agents:
        _local_name(nodes[aid], local_of)

    # Header — only include the classes we actually use.
    used_agent_classes = sorted({_AGENT_CLASS[nodes[a].kind] for a in agent_ids})
    tool_classes: set[str] = set()
    for e in graph.edges:
        if e.kind == "wraps_agent" and e.target in nodes:
            tool_classes.add("AgentTool")
    has_graph_edges = any(e.kind == "graph_edge" for e in graph.edges)

    header: list[str] = ['"""Emitted by adk_parser.codegen. Round-trip target."""']
    if used_agent_classes:
        header.append(f"from google.adk.agents import {', '.join(used_agent_classes)}")
    if tool_classes:
        header.append(f"from google.adk.tools import {', '.join(sorted(tool_classes))}")
    if has_graph_edges:
        header.append("from google.adk.workflows import Graph")
    header.append("")

    body: list[str] = []
    body.extend(_emit_tool_stubs(tool_nodes))
    body.extend(_emit_callback_stubs(cb_nodes))

    for aid in ordered_agents:
        node = nodes[aid]
        local = local_of[aid]
        call = _agent_call(node, graph.edges, nodes, local_of)
        body.append(f"{local} = {call}")
        body.append("")

    body.extend(_graph_builder_blocks(graph, local_of))

    return "\n".join(header + body).rstrip() + "\n"
