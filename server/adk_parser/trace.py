"""Trace overlay: turn a stream of runtime spans into an observed graph
that can be diffed against the static extractor's output.

The idea: a user instruments their running ADK app with ``tracer.py`` (or
any OTel-compatible collector), exports spans as JSON, and posts them to
``/traces``. This module builds a normalized observed graph from those
spans; ``overlay.py`` diffs it against the static graph and tags each
edge's status.

Spans are opinionated but light — enough to reconstruct the workflow
without pulling in the OTel SDK. A minimal Span carries kind + name +
parent id, so `(parent.kind, parent.name) → (child.kind, child.name)`
gives one observed edge.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SpanKind = Literal["agent", "tool_call", "callback"]


class Span(BaseModel):
    id: str
    kind: SpanKind
    name: str
    parent_id: str | None = None
    started_at: float = 0.0
    ended_at: float | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    spans: list[Span] = Field(default_factory=list)


# One observed edge: (parent_kind, parent_name, child_kind, child_name, edge_kind)
ObservedEdge = tuple[str, str, str, str, str]

# One observed node: (kind, name)
ObservedNode = tuple[str, str]


_SPAN_KIND_TO_NODE_KIND = {
    "agent": "agent",  # normalized; we don't know the exact sub-kind at trace time
    "tool_call": "tool",
    "callback": "callback",
}


def _edge_kind(parent_kind: str, child_kind: str, child_attrs: dict[str, Any]) -> str | None:
    """Pick the graph edge kind that matches this parent→child relationship."""
    if parent_kind == "agent" and child_kind == "agent":
        return "owns_subagent"
    if parent_kind == "agent" and child_kind == "tool_call":
        # Tool wrapping an agent is `wraps_agent` in the static schema.
        if child_attrs.get("wraps_agent"):
            return "wraps_agent"
        return "uses_tool"
    if parent_kind == "agent" and child_kind == "callback":
        return "hook"
    return None


def observed_from_spans(trace: Trace) -> tuple[set[ObservedNode], set[ObservedEdge]]:
    """Extract the (nodes, edges) implied by a trace.

    Nodes are stored as ``(node_kind, name)`` where ``node_kind`` matches the
    static schema's `NodeKind` prefixes (``agent`` covers all agent kinds;
    the static side does the fine-grained matching). Edges are 5-tuples so
    a set can dedupe repeated identical events cleanly.
    """
    by_id: dict[str, Span] = {s.id: s for s in trace.spans}

    nodes: set[ObservedNode] = set()
    edges: set[ObservedEdge] = set()

    for span in trace.spans:
        node_kind = _SPAN_KIND_TO_NODE_KIND.get(span.kind)
        if node_kind is None:
            continue
        nodes.add((node_kind, span.name))

        if span.parent_id is None:
            continue
        parent = by_id.get(span.parent_id)
        if parent is None:
            continue
        parent_kind = _SPAN_KIND_TO_NODE_KIND.get(parent.kind)
        if parent_kind is None:
            continue

        edge_kind = _edge_kind(parent.kind, span.kind, span.attrs)
        if edge_kind is None:
            continue
        edges.add((parent_kind, parent.name, node_kind, span.name, edge_kind))

    return nodes, edges
