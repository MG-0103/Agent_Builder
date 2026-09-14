from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

NodeKind = Literal[
    "llm_agent",
    "sequential_agent",
    "parallel_agent",
    "loop_agent",
    "custom_agent",
    "tool_function",
    "tool_builtin",
    "tool_mcp",
    "agent_as_tool",
    "callback",
]

EdgeKind = Literal[
    "owns_subagent",
    "uses_tool",
    "wraps_agent",
    "hook",
    "graph_edge",
    "shares_state",
]


class Provenance(BaseModel):
    file: str
    line: int
    col: int = 0


class Node(BaseModel):
    id: str
    kind: NodeKind
    name: str
    provenance: Optional[Provenance] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    id: str
    source: str
    target: str
    kind: EdgeKind
    meta: dict[str, Any] = Field(default_factory=dict)


class Graph(BaseModel):
    version: str = "0.1"
    source_root: str
    framework: str = "google-adk"
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    unresolved: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
