"""Graph → ADK Python source emitter.

Two output modes:

- ``emit_python(graph) -> str``: single-file emit. One Python module
  reproducing the whole workflow. Used to prove parse → emit → parse
  parity on fixtures.
- ``emit_layout(graph) -> dict[str, str]``: layout-preserving emit.
  Groups nodes by their original ``provenance.file`` and emits one
  module per source file, with cross-file imports computed from the
  graph. Generated code is wrapped in
  ``# region agentbuilder:generated`` markers; ``apply_region()`` merges
  it into existing files without touching hand-edited code outside the
  region.

Non-round-trippable node kinds (raise ``EmitSkipped`` when hit):
- ``custom_agent``: the user's subclass isn't importable from ADK.
- ``tool_mcp``: external toolset with runtime-only shape.
- tool_function nodes marked ``meta.dynamic`` or named ``<unresolved>``.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .schema import Edge, Graph, Node


REGION_START = "# region agentbuilder:generated"
REGION_END = "# endregion agentbuilder:generated"


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


# ---- Layout-preserving emit ---------------------------------------------


def _fq_module_of(node: Node) -> str:
    """Extract the fq_module the adapter used for this node.

    Node ids follow ``<fq_module>:<kind_short>:<name>``. Splitting from the
    right on ``:`` twice recovers the module. Nodes we can't emit
    (``unresolved_tool``, malformed) never reach layout emit.
    """
    parts = node.id.rsplit(":", 2)
    return parts[0] if len(parts) == 3 else node.id


def _relpath_of(node: Node, source_root: Path) -> str | None:
    if node.provenance is None:
        return None
    try:
        return str(Path(node.provenance.file).resolve().relative_to(source_root))
    except ValueError:
        return None


def apply_region(existing: str, generated_body: str) -> str:
    """Splice ``generated_body`` into ``existing`` inside a region block.

    - Replaces any single existing ``REGION_START`` .. ``REGION_END`` block
      (inclusive) with a freshly wrapped one.
    - If no region is present, appends a new one at the end.
    - Content outside the region is preserved verbatim.
    """
    block = f"{REGION_START}\n{generated_body.rstrip()}\n{REGION_END}\n"
    if REGION_START in existing and REGION_END in existing:
        start = existing.index(REGION_START)
        end = existing.index(REGION_END, start) + len(REGION_END)
        # Consume the newline right after REGION_END if present.
        if end < len(existing) and existing[end] == "\n":
            end += 1
        return existing[:start] + block + existing[end:]
    if not existing:
        return block
    sep = "" if existing.endswith("\n") else "\n"
    return f"{existing}{sep}\n{block}"


def _emit_file(
    rel_path: str,
    module_nodes: dict[str, list[Node]],
    node_module: dict[str, str],
    node_local: dict[str, str],
    graph: Graph,
    nodes_by_id: dict[str, Node],
    ordered_agent_ids: list[str],
) -> str:
    """Emit the body of one module (everything that goes inside the region).

    ``module_nodes[fq]`` = nodes provenance-owned by module ``fq``.
    ``node_module[nid]`` = fq_module of a node's provenance file.
    ``node_local[nid]``  = local Python name used for that node.
    """
    fq = _relpath_to_fq(rel_path)
    owned = module_nodes.get(fq, [])
    owned_ids = {n.id for n in owned}

    # Split owned nodes by kind, preserving global emit order.
    tool_nodes = [n for n in owned if n.kind == "tool_function"]
    cb_nodes = [n for n in owned if n.kind == "callback"]
    agent_ids_here = [aid for aid in ordered_agent_ids if aid in owned_ids]

    # Cross-file imports: any edge from an agent in this file to a target
    # node whose module differs from ours becomes a `from <fq> import <local>`.
    # `agent_as_tool` nodes themselves live in the file that references them
    # (that's how the adapter tagged their provenance), but they wrap an agent
    # that may live in another file — walk `meta.wraps` for that.
    imports_by_module: dict[str, set[str]] = defaultdict(set)

    def _import(target_id: str) -> None:
        target_mod = node_module.get(target_id)
        if not target_mod or target_mod == fq:
            return
        local = node_local.get(target_id)
        if not local:
            return
        imports_by_module[target_mod].add(local)

    for aid in agent_ids_here:
        for e in graph.edges:
            if e.source != aid:
                continue
            if e.target not in nodes_by_id:
                continue
            if e.kind in ("uses_tool", "wraps_agent", "owns_subagent"):
                _import(e.target)
                if e.kind == "wraps_agent":
                    wrapped = nodes_by_id[e.target].meta.get("wraps")
                    if isinstance(wrapped, str) and wrapped in nodes_by_id:
                        _import(wrapped)
            elif e.kind == "hook":
                _import(e.target)

    # ADK class imports, only for what this file uses.
    agent_classes = sorted(
        {_AGENT_CLASS[nodes_by_id[aid].kind] for aid in agent_ids_here}
    )
    tool_classes: set[str] = set()
    for aid in agent_ids_here:
        for e in graph.edges:
            if e.source == aid and e.kind == "wraps_agent" and e.target in nodes_by_id:
                tool_classes.add("AgentTool")
    file_has_graph_builder = any(
        e.kind == "graph_edge" and _module_of_endpoint(e.source, node_module) == fq
        for e in graph.edges
    )

    lines: list[str] = []
    if agent_classes:
        lines.append(f"from google.adk.agents import {', '.join(agent_classes)}")
    if tool_classes:
        lines.append(f"from google.adk.tools import {', '.join(sorted(tool_classes))}")
    if file_has_graph_builder:
        lines.append("from google.adk.workflows import Graph")
    for target_mod in sorted(imports_by_module):
        names = ", ".join(sorted(imports_by_module[target_mod]))
        lines.append(f"from {target_mod} import {names}")
    if lines:
        lines.append("")

    lines.extend(_emit_tool_stubs(tool_nodes))
    lines.extend(_emit_callback_stubs(cb_nodes))

    for aid in agent_ids_here:
        node = nodes_by_id[aid]
        local = node_local[aid]
        call = _agent_call(node, graph.edges, nodes_by_id, node_local)
        lines.append(f"{local} = {call}")
        lines.append("")

    # Graph builder blocks land in the file whose module owns the builder's
    # first edge (there is no dedicated builder node in the schema today; a
    # single-file placement is close enough for round-trip).
    if file_has_graph_builder:
        lines.extend(_graph_builder_blocks(graph, node_local))

    return "\n".join(lines).rstrip() + "\n"


def _module_of_endpoint(node_id: str, node_module: dict[str, str]) -> str | None:
    return node_module.get(node_id)


def _relpath_to_fq(rel_path: str) -> str:
    """Turn ``pkg/researcher.py`` into ``pkg.researcher``; ``pkg/__init__.py``
    into ``pkg``."""
    p = Path(rel_path)
    parts = list(p.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = p.stem
    return ".".join(parts)


def _fq_to_relpath(fq: str) -> str:
    return "/".join(fq.split(".")) + ".py"


def emit_layout(graph: Graph) -> dict[str, str]:
    """Layout-preserving emit.

    Returns a mapping of repo-relative path → the content of the file's
    ``agentbuilder:generated`` region body. Callers merge each body into
    the corresponding on-disk file via ``apply_region``.
    """
    nodes = _by_id(graph.nodes)

    # Same guardrails as flat emit: refuse non-round-trippable shapes early.
    if any(n.kind == "custom_agent" for n in graph.nodes):
        raise EmitSkipped("custom_agent kinds present")
    if any(n.kind == "tool_mcp" for n in graph.nodes):
        raise EmitSkipped("tool_mcp present")
    for w in graph.warnings:
        if isinstance(w, dict) and w.get("kind") == "dynamic_tools":
            raise EmitSkipped("dynamic_tools warning; parser gave up on a tool list")
    for t in graph.nodes:
        if t.kind == "tool_function" and t.name == "<unresolved>":
            raise EmitSkipped("unresolved tool present")

    agent_ids = [n.id for n in graph.nodes if n.kind in _AGENT_CLASS]
    ordered_agent_ids = _topo_agents(agent_ids, graph.edges)

    node_module: dict[str, str] = {n.id: _fq_module_of(n) for n in graph.nodes}
    module_nodes: dict[str, list[Node]] = defaultdict(list)
    for n in graph.nodes:
        module_nodes[node_module[n.id]].append(n)

    # Global local-name map, allocated in the same order as flat emit so
    # cross-file imports have a stable name to import.
    node_local: dict[str, str] = {}
    for n in graph.nodes:
        if n.kind == "tool_function":
            _local_name(n, node_local)
    for n in graph.nodes:
        if n.kind == "callback":
            _local_name(n, node_local)
    for aid in ordered_agent_ids:
        _local_name(nodes[aid], node_local)

    files: dict[str, str] = {}
    for fq in sorted(module_nodes):
        rel = _fq_to_relpath(fq)
        body = _emit_file(
            rel_path=rel,
            module_nodes=module_nodes,
            node_module=node_module,
            node_local=node_local,
            graph=graph,
            nodes_by_id=nodes,
            ordered_agent_ids=ordered_agent_ids,
        )
        files[rel] = body

    return files
