"""Parent-side runtime probe: run the inspector in a subprocess and merge
its observations into a static Graph."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .schema import Edge, Graph, Node


def run_probe(repo_path: str | Path, entry_module: str, timeout: float = 30.0) -> dict[str, Any]:
    repo = Path(repo_path).expanduser().resolve()
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo}{os.pathsep}{env.get('PYTHONPATH', '')}"
    proc = subprocess.run(
        [sys.executable, "-m", "adk_parser._inspector", entry_module],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(repo),
    )
    if proc.returncode != 0 and not proc.stdout:
        return {"nodes": [], "edges": [], "errors": [proc.stderr.strip() or "probe failed"]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"nodes": [], "edges": [], "errors": [f"invalid probe output: {proc.stdout[:200]}"]}


def merge(graph: Graph, observed: dict[str, Any]) -> Graph:
    """Fold a runtime fragment into `graph` in place. Return the same graph.

    Matching by name: if the runtime sees an agent named `researcher` and the
    static graph has one too, mark it observed; otherwise add a `runtime:<name>`
    node. Edges dedup by (source, target, kind).
    """
    name_to_id: dict[str, str] = {}
    for n in graph.nodes:
        name_to_id.setdefault(n.name, n.id)

    for rn in observed.get("nodes", []):
        name = rn["name"]
        if name in name_to_id:
            static_node = next(n for n in graph.nodes if n.id == name_to_id[name])
            static_node.meta["observed"] = True
        else:
            new_id = f"runtime:{name}"
            graph.nodes.append(
                Node(
                    id=new_id,
                    kind=rn.get("kind", "custom_agent"),
                    name=name,
                    meta={"observed": True, "runtime_only": True},
                )
            )
            name_to_id[name] = new_id

    existing_edges: set[tuple[str, str, str]] = {(e.source, e.target, e.kind) for e in graph.edges}

    for re in observed.get("edges", []):
        src_name = re["source_name"]
        tgt_name = re["target_name"]
        kind = re["kind"]
        src = name_to_id.get(src_name)
        tgt = name_to_id.get(tgt_name)
        if not src:
            src = f"runtime:{src_name}"
            graph.nodes.append(Node(id=src, kind="custom_agent", name=src_name,
                                     meta={"observed": True, "runtime_only": True}))
            name_to_id[src_name] = src
        if not tgt:
            # Tool/sub-agent not seen statically. Emit a tool_function node as a
            # reasonable default; caller can refine by kind if needed.
            tgt = f"runtime:{tgt_name}"
            graph.nodes.append(Node(id=tgt,
                                     kind="tool_function" if kind == "uses_tool" else "custom_agent",
                                     name=tgt_name,
                                     meta={"observed": True, "runtime_only": True}))
            name_to_id[tgt_name] = tgt
        key = (src, tgt, kind)
        if key in existing_edges:
            # Existing static edge; tag observed.
            for e in graph.edges:
                if (e.source, e.target, e.kind) == key:
                    e.meta["observed"] = True
                    break
        else:
            graph.edges.append(
                Edge(id=f"{src}->{tgt}:{kind}:observed",
                     source=src, target=tgt, kind=kind,
                     meta={"observed": True, "runtime_only": True})
            )
            existing_edges.add(key)

    if observed.get("errors"):
        graph.warnings.append({"kind": "probe_error", "errors": observed["errors"]})
    return graph
