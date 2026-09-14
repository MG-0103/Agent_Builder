"""Google ADK static extractor.

Pipeline:
  Pass 1: import + symbol index (per-module alias + import maps)
  Pass 2: agent instantiation extraction (records local top-level symbols)
  Pass 3: tool + callback resolution
  Pass 4: cross-file symbol resolution (rewrites `ref:<name>` placeholders)
  Pass 5: unresolved marker
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .schema import Edge, Graph, Node, Provenance

ADK_MODULE_PREFIX = "google.adk"
PLACEHOLDER_PREFIX = "__ref__:"

AGENT_CLASSES = {
    "LlmAgent": "llm_agent",
    "Agent": "llm_agent",
    "SequentialAgent": "sequential_agent",
    "ParallelAgent": "parallel_agent",
    "LoopAgent": "loop_agent",
    "BaseAgent": "custom_agent",
}

GRAPH_BUILDER_CLASSES = {"Graph", "Workflow", "StateGraph"}

CALLBACK_KWARGS = {
    "before_agent_callback",
    "after_agent_callback",
    "before_model_callback",
    "after_model_callback",
    "before_tool_callback",
    "after_tool_callback",
}


@dataclass
class ModuleIndex:
    path: Path
    fq_module: str
    is_package: bool
    tree: ast.Module
    adk_aliases: dict[str, str] = field(default_factory=dict)
    # local_name -> (source_module_fq, name_in_source). name_in_source == local_name
    # for `from x import y` when no alias; for `import x` local_name == x.
    imports: dict[str, tuple[str, str]] = field(default_factory=dict)
    # local top-level name -> node_id (populated during extraction)
    symbols: dict[str, str] = field(default_factory=dict)
    # local class name -> resolved agent kind (populated pre-extraction)
    custom_agents: dict[str, str] = field(default_factory=dict)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def _module_fq(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(base_fq: str, is_package: bool, module: str | None, level: int) -> str:
    if level == 0:
        return module or ""
    # From CPython's semantics: `from .x import y` in a package __init__ resolves
    # relative to the package itself, but the same statement inside a module
    # `pkg.mod` resolves relative to `pkg`. Normalize by adding one virtual climb
    # for non-package modules.
    climbs = level if is_package else level
    if not is_package:
        # `pkg.mod` with level=1 -> anchor `pkg`
        climbs = level
        base_parts = base_fq.split(".") if base_fq else []
        anchor = base_parts[:-climbs] if climbs <= len(base_parts) else []
    else:
        # `pkg` (init) with level=1 -> anchor `pkg`; level=2 -> parent of `pkg`.
        base_parts = base_fq.split(".") if base_fq else []
        extra = level - 1
        anchor = base_parts[:len(base_parts) - extra] if extra <= len(base_parts) else []
    if module:
        anchor = anchor + module.split(".")
    return ".".join(anchor)


def _build_import_tables(tree: ast.Module, fq_module: str, is_package: bool) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Return (adk_aliases, imports).

    - adk_aliases: local_name -> qualified ADK path (e.g. 'google.adk.agents.LlmAgent')
    - imports: local_name -> (source_module_fq, name_in_source) for non-ADK imports.
      Used to chase cross-file symbol refs.
    """
    adk: dict[str, str] = {}
    imp: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source = _resolve_relative(fq_module, is_package, node.module, node.level or 0)
            for alias in node.names:
                local = alias.asname or alias.name
                if source.startswith(ADK_MODULE_PREFIX):
                    adk[local] = f"{source}.{alias.name}"
                else:
                    imp[local] = (source, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name
                if alias.name.startswith(ADK_MODULE_PREFIX):
                    adk[local] = alias.name
                else:
                    imp[local] = (alias.name, local)
    return adk, imp


def _base_kind(base: ast.expr, mod: ModuleIndex) -> str | None:
    """Resolve a class base to an agent kind, if any."""
    if isinstance(base, ast.Name):
        qual = mod.adk_aliases.get(base.id)
        if qual:
            short = qual.rsplit(".", 1)[-1]
            if short in AGENT_CLASSES:
                return AGENT_CLASSES[short]
        # Local custom class already resolved.
        if base.id in mod.custom_agents:
            return mod.custom_agents[base.id]
    elif isinstance(base, ast.Attribute):
        if base.attr in AGENT_CLASSES:
            return AGENT_CLASSES[base.attr]
    return None


def _index_custom_agent_classes(mod: ModuleIndex) -> None:
    """Populate mod.custom_agents. Fixed-point over ClassDefs for transitive bases."""
    classdefs = [n for n in mod.tree.body if isinstance(n, ast.ClassDef)]
    changed = True
    while changed:
        changed = False
        for cls in classdefs:
            if cls.name in mod.custom_agents:
                continue
            for base in cls.bases:
                kind = _base_kind(base, mod)
                if kind:
                    mod.custom_agents[cls.name] = kind
                    changed = True
                    break


def _resolve_call_name(call: ast.Call, aliases: dict[str, str]) -> str | None:
    """Return the ADK short class name (e.g. 'LlmAgent'), honoring `as` aliases."""
    func = call.func
    if isinstance(func, ast.Name):
        qual = aliases.get(func.id)
        if qual and qual.startswith(ADK_MODULE_PREFIX):
            return qual.rsplit(".", 1)[-1]
    elif isinstance(func, ast.Attribute):
        return func.attr
    return None


def parse_path(root: str | Path) -> Graph:
    root = Path(root).resolve()
    graph = Graph(source_root=str(root))

    modules: list[ModuleIndex] = []
    for py in _iter_python_files(root):
        try:
            tree = ast.parse(py.read_text(), filename=str(py))
        except SyntaxError:
            continue
        fq = _module_fq(root, py)
        is_pkg = py.name == "__init__.py"
        adk, imp = _build_import_tables(tree, fq, is_pkg)
        modules.append(ModuleIndex(path=py, fq_module=fq, is_package=is_pkg, tree=tree, adk_aliases=adk, imports=imp))

    for mod in modules:
        _index_custom_agent_classes(mod)

    for mod in modules:
        _extract_agents(mod, graph)

    for mod in modules:
        _extract_graph_builders(mod, graph)

    _resolve_cross_file(modules, graph)
    return graph


def _top_level_assign_name(tree: ast.Module, call: ast.Call) -> str | None:
    """If `call` is the RHS of a module-level `name = call`, return name."""
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and stmt.value is call:
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                return stmt.targets[0].id
    return None


def _extract_agents(mod: ModuleIndex, graph: Graph) -> None:
    for node in ast.walk(mod.tree):
        if not isinstance(node, ast.Call):
            continue
        cls = _resolve_call_name(node, mod.adk_aliases)
        kind: str | None = None
        if cls in AGENT_CLASSES:
            kind = AGENT_CLASSES[cls]
        elif isinstance(node.func, ast.Name) and node.func.id in mod.custom_agents:
            cls = node.func.id
            kind = mod.custom_agents[cls]
        if not kind:
            continue

        agent_local = _top_level_assign_name(mod.tree, node)
        name = _kwarg_str(node, "name") or agent_local or f"anon_{node.lineno}"
        agent_id = f"{mod.fq_module or mod.path.name}:{name}:{node.lineno}"

        graph.nodes.append(
            Node(
                id=agent_id,
                kind=kind,
                name=name,
                provenance=Provenance(file=str(mod.path), line=node.lineno, col=node.col_offset),
                meta={"class": cls, "model": _kwarg_str(node, "model")},
            )
        )
        if agent_local:
            mod.symbols[agent_local] = agent_id

        _extract_tools(node, agent_id, mod, graph)
        _extract_sub_agents(node, agent_id, mod, graph)
        _extract_callbacks(node, agent_id, mod, graph)


def _kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _kwarg_str(call: ast.Call, name: str) -> str | None:
    val = _kwarg(call, name)
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
        return val.value
    return None


def _placeholder(mod: ModuleIndex, local_name: str) -> str:
    return f"{PLACEHOLDER_PREFIX}{mod.fq_module}::{local_name}"


def _extract_tools(call: ast.Call, agent_id: str, mod: ModuleIndex, graph: Graph) -> None:
    tools = _kwarg(call, "tools")
    if not isinstance(tools, ast.List):
        if tools is not None:
            graph.unresolved.append(
                {"agent": agent_id, "field": "tools", "reason": "non-literal", "file": str(mod.path), "line": call.lineno}
            )
        return
    for i, elt in enumerate(tools.elts):
        tool_id, tool_node, edge_kind = _resolve_tool_elt(elt, mod, i)
        if tool_node:
            graph.nodes.append(tool_node)
        graph.edges.append(
            Edge(
                id=f"{agent_id}->{tool_id}:tool:{i}",
                source=agent_id,
                target=tool_id,
                kind=edge_kind,
                meta={"index": i},
            )
        )


def _resolve_tool_elt(elt: ast.expr, mod: ModuleIndex, idx: int) -> tuple[str, Node | None, str]:
    if isinstance(elt, ast.Name):
        tid = f"{mod.fq_module}:tool:{elt.id}"
        node = Node(
            id=tid,
            kind="tool_function",
            name=elt.id,
            provenance=Provenance(file=str(mod.path), line=elt.lineno),
        )
        mod.symbols.setdefault(elt.id, tid)
        return tid, node, "uses_tool"

    if isinstance(elt, ast.Call):
        cls = _resolve_call_name(elt, mod.adk_aliases) or _call_attr_name(elt)
        if cls == "AgentTool":
            wrapped = _kwarg(elt, "agent") or (elt.args[0] if elt.args else None)
            if isinstance(wrapped, ast.Name):
                target = _placeholder(mod, wrapped.id)
                tid = f"{mod.fq_module}:agent_as_tool:{wrapped.id}:{elt.lineno}"
                node = Node(
                    id=tid,
                    kind="agent_as_tool",
                    name=wrapped.id,
                    provenance=Provenance(file=str(mod.path), line=elt.lineno),
                    meta={"wraps_ref": target},
                )
                return tid, node, "wraps_agent"
        if cls == "FunctionTool":
            fn = _kwarg(elt, "func") or (elt.args[0] if elt.args else None)
            fn_name = fn.id if isinstance(fn, ast.Name) else f"anon_{elt.lineno}"
            tid = f"{mod.fq_module}:tool:{fn_name}"
            node = Node(
                id=tid,
                kind="tool_function",
                name=fn_name,
                provenance=Provenance(file=str(mod.path), line=elt.lineno),
            )
            if isinstance(fn, ast.Name):
                mod.symbols.setdefault(fn.id, tid)
            return tid, node, "uses_tool"
        if cls == "MCPToolset":
            tid = f"{mod.fq_module}:mcp:{elt.lineno}"
            return tid, Node(
                id=tid,
                kind="tool_mcp",
                name="MCPToolset",
                provenance=Provenance(file=str(mod.path), line=elt.lineno),
                meta={"external": True},
            ), "uses_tool"

    tid = f"{mod.fq_module}:unresolved_tool:{idx}:{getattr(elt, 'lineno', 0)}"
    return tid, Node(
        id=tid,
        kind="tool_function",
        name="<unresolved>",
        provenance=Provenance(file=str(mod.path), line=getattr(elt, "lineno", 0)),
        meta={"dynamic": True},
    ), "uses_tool"


def _call_attr_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _extract_sub_agents(call: ast.Call, agent_id: str, mod: ModuleIndex, graph: Graph) -> None:
    subs = _kwarg(call, "sub_agents")
    if not isinstance(subs, ast.List):
        return
    for i, elt in enumerate(subs.elts):
        if isinstance(elt, ast.Name):
            target = _placeholder(mod, elt.id)
            graph.edges.append(
                Edge(
                    id=f"{agent_id}->{elt.id}:sub:{i}",
                    source=agent_id,
                    target=target,
                    kind="owns_subagent",
                    meta={"order": i, "symbol": elt.id},
                )
            )


def _extract_callbacks(call: ast.Call, agent_id: str, mod: ModuleIndex, graph: Graph) -> None:
    for kw in call.keywords:
        if kw.arg not in CALLBACK_KWARGS:
            continue
        if isinstance(kw.value, ast.Name):
            cb_name = kw.value.id
            cb_id = f"{mod.fq_module}:cb:{cb_name}"
            if not any(n.id == cb_id for n in graph.nodes):
                graph.nodes.append(
                    Node(
                        id=cb_id,
                        kind="callback",
                        name=cb_name,
                        provenance=Provenance(file=str(mod.path), line=kw.value.lineno),
                        meta={"phase": kw.arg},
                    )
                )
            mod.symbols.setdefault(cb_name, cb_id)
            graph.edges.append(
                Edge(
                    id=f"{agent_id}->{cb_id}:hook",
                    source=agent_id,
                    target=cb_id,
                    kind="hook",
                    meta={"phase": kw.arg},
                )
            )


# ---- Graph API extractor -------------------------------------------------


def _is_graph_builder_call(call: ast.Call, aliases: dict[str, str]) -> str | None:
    """Return short class name if `call` constructs an ADK graph builder."""
    func = call.func
    if isinstance(func, ast.Name):
        qual = aliases.get(func.id)
        if qual and qual.startswith(ADK_MODULE_PREFIX):
            short = qual.rsplit(".", 1)[-1]
            if short in GRAPH_BUILDER_CLASSES:
                return short
    elif isinstance(func, ast.Attribute) and func.attr in GRAPH_BUILDER_CLASSES:
        return func.attr
    return None


def _extract_graph_builders(mod: ModuleIndex, graph: Graph) -> None:
    """Detect `g = Graph()` + subsequent `.add_node/.add_edge/.add_conditional_edges`."""
    builders: dict[str, dict] = {}

    for stmt in mod.tree.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            cls = _is_graph_builder_call(stmt.value, mod.adk_aliases)
            if cls and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                var = stmt.targets[0].id
                builders[var] = {"class": cls, "labels": {}, "line": stmt.lineno}

    if not builders:
        return

    for node in ast.walk(mod.tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        recv = node.func.value
        if not isinstance(recv, ast.Name) or recv.id not in builders:
            continue
        method = node.func.attr
        b = builders[recv.id]

        if method == "add_node":
            _gb_add_node(node, b, mod)
        elif method == "add_edge":
            _gb_add_edge(node, b, mod, graph)
        elif method == "add_conditional_edges":
            _gb_conditional(node, b, mod, graph)
        elif method == "set_entry_point":
            _gb_entry_point(node, b, mod, graph)


def _gb_add_node(call: ast.Call, builder: dict, mod: ModuleIndex) -> None:
    """`gb.add_node("label", agent)` or `gb.add_node("label", node=agent)`."""
    args = call.args
    label = None
    agent_expr: ast.expr | None = None

    if args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
        label = args[0].value
    if len(args) >= 2:
        agent_expr = args[1]
    for kw in call.keywords:
        if kw.arg in {"name", "label"} and isinstance(kw.value, ast.Constant):
            label = kw.value.value
        elif kw.arg in {"node", "agent", "action"}:
            agent_expr = kw.value

    if not label:
        return

    target_id: str | None = None
    if isinstance(agent_expr, ast.Name):
        target_id = _placeholder(mod, agent_expr.id)

    builder["labels"][label] = target_id


def _resolve_endpoint(expr: ast.expr, builder: dict, mod: ModuleIndex) -> str | None:
    """Resolve a `add_edge` endpoint to a placeholder or already-known id."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return builder["labels"].get(expr.value)
    if isinstance(expr, ast.Name):
        return _placeholder(mod, expr.id)
    return None


def _gb_add_edge(call: ast.Call, builder: dict, mod: ModuleIndex, graph: Graph) -> None:
    args = call.args
    if len(args) < 2:
        return
    src = _resolve_endpoint(args[0], builder, mod)
    tgt = _resolve_endpoint(args[1], builder, mod)
    if not src or not tgt:
        graph.unresolved.append(
            {"reason": "graph_edge endpoint", "file": str(mod.path), "line": call.lineno}
        )
        return

    condition = None
    for kw in call.keywords:
        if kw.arg == "condition" and isinstance(kw.value, ast.Name):
            condition = kw.value.id

    graph.edges.append(
        Edge(
            id=f"{mod.fq_module}:graph:{call.lineno}",
            source=src,
            target=tgt,
            kind="graph_edge",
            meta={"condition": condition} if condition else {},
        )
    )


def _gb_conditional(call: ast.Call, builder: dict, mod: ModuleIndex, graph: Graph) -> None:
    """`gb.add_conditional_edges(src, router, {"case_a": "label_a", ...})`."""
    args = call.args
    if len(args) < 2:
        return
    src = _resolve_endpoint(args[0], builder, mod)
    if not src:
        return

    router = args[1].id if isinstance(args[1], ast.Name) else None
    mapping = args[2] if len(args) >= 3 else None
    if isinstance(mapping, ast.Dict):
        for k, v in zip(mapping.keys, mapping.values):
            if isinstance(v, (ast.Constant,)) and isinstance(v.value, str):
                tgt = builder["labels"].get(v.value)
                if not tgt:
                    continue
                case = k.value if isinstance(k, ast.Constant) else None
                graph.edges.append(
                    Edge(
                        id=f"{mod.fq_module}:cond:{call.lineno}:{case}",
                        source=src,
                        target=tgt,
                        kind="graph_edge",
                        meta={"router": router, "case": case, "dynamic": True},
                    )
                )
    else:
        graph.unresolved.append(
            {"reason": "conditional mapping not literal", "file": str(mod.path), "line": call.lineno, "router": router}
        )


def _gb_entry_point(call: ast.Call, builder: dict, mod: ModuleIndex, graph: Graph) -> None:
    if not call.args:
        return
    arg = call.args[0]
    if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
        return
    tgt = builder["labels"].get(arg.value)
    if not tgt:
        return
    pending = getattr(graph, "_entry_pending", None)
    if pending is None:
        pending = []
        # Pydantic BaseModel disallows unknown attrs by default; assign via __dict__.
        object.__setattr__(graph, "_entry_pending", pending)
    pending.append(tgt)


# ---- Pass 4: cross-file resolver -----------------------------------------


def _resolve_cross_file(modules: list[ModuleIndex], graph: Graph) -> None:
    by_fq = {m.fq_module: m for m in modules}

    def lookup(module_fq: str, local_name: str, seen: set[tuple[str, str]] | None = None) -> str | None:
        seen = seen or set()
        key = (module_fq, local_name)
        if key in seen:
            return None
        seen.add(key)

        mod = by_fq.get(module_fq)
        if not mod:
            return None

        # Local top-level symbol wins.
        if local_name in mod.symbols:
            return mod.symbols[local_name]

        # Chase through imports.
        if local_name in mod.imports:
            source_mod, source_name = mod.imports[local_name]
            return lookup(source_mod, source_name, seen)

        return None

    def _resolve_placeholder(value: str) -> str | None:
        payload = value[len(PLACEHOLDER_PREFIX):]
        module_fq, local = payload.split("::", 1)
        return lookup(module_fq, local)

    for edge in graph.edges:
        for endpoint in ("source", "target"):
            val = getattr(edge, endpoint)
            if val.startswith(PLACEHOLDER_PREFIX):
                resolved = _resolve_placeholder(val)
                if resolved:
                    setattr(edge, endpoint, resolved)
                else:
                    payload = val[len(PLACEHOLDER_PREFIX):]
                    module_fq, local = payload.split("::", 1)
                    graph.unresolved.append(
                        {"edge": edge.id, "endpoint": endpoint, "reason": "symbol not found",
                         "module": module_fq, "symbol": local}
                    )

    # Apply pending entry-point markers now that placeholders resolved.
    for pending in list(getattr(graph, "_entry_pending", []) or []):
        target = pending
        if target.startswith(PLACEHOLDER_PREFIX):
            resolved = _resolve_placeholder(target)
            target = resolved or target
        for n in graph.nodes:
            if n.id == target:
                n.meta["entry_point"] = True
                break

    # Resolve AgentTool wraps_ref meta too.
    for node in graph.nodes:
        ref = node.meta.get("wraps_ref") if isinstance(node.meta, dict) else None
        if isinstance(ref, str) and ref.startswith(PLACEHOLDER_PREFIX):
            payload = ref[len(PLACEHOLDER_PREFIX):]
            module_fq, local = payload.split("::", 1)
            resolved = lookup(module_fq, local)
            if resolved:
                node.meta["wraps"] = resolved
            node.meta.pop("wraps_ref", None)
