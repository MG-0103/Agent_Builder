"""Wire types for the auto-probe. Kept in one file so the client can mirror
them from a single source when we start rendering coverage in the canvas."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


StubMode = Literal["real", "schema", "semantic", "user"]


class ToolStubConfig(BaseModel):
    """Per-tool override. Keyed by qualified tool name (module:tool_name)."""
    mode: StubMode = "semantic"
    canned: Any | None = None  # for mode="user" — return this value directly
    callable_path: str | None = None  # for mode="user" — dotted path to a fn


class RunConfig(BaseModel):
    """Everything the orchestrator needs to know to plan a run."""
    repo_path: str
    entry_module: str
    entry_object: str | None = None
    # Total wall-clock budget in seconds (soft cap — cuts at next session end).
    budget_seconds: float = 600.0
    # Cost cap in dollars (soft). None disables.
    budget_usd: float | None = None
    # Per-session turn cap. Default 6 matches typical multi-turn workflows.
    max_turns_per_session: int = 6
    # Stop after N consecutive sessions with no new edge coverage.
    plateau_sessions: int = 3
    # Default stub mode for tools without an entry in `tool_stubs`.
    default_stub_mode: StubMode = "semantic"
    tool_stubs: dict[str, ToolStubConfig] = Field(default_factory=dict)


class InvokeRequest(BaseModel):
    """Single-shot: run one query in one session and return the trace."""
    repo_path: str
    entry_module: str
    entry_object: str | None = None
    query: str
    session_id: str | None = None
    default_stub_mode: StubMode = "semantic"
    tool_stubs: dict[str, ToolStubConfig] = Field(default_factory=dict)


class TurnRecord(BaseModel):
    """One user query and the trace it produced."""
    user_query: str
    spans: list[dict[str, Any]]  # raw Trace.spans


class SessionRecord(BaseModel):
    session_id: str
    turns: list[TurnRecord]
    edges_fired: list[str]  # edge ids from the static graph, deduped
    ended_because: Literal["turn_budget", "generator_ended", "agent_ended", "coverage_plateau", "error"]


class RunSummary(BaseModel):
    run_id: str
    status: Literal["running", "done", "error", "cancelled"]
    coverage: dict[str, int]  # edge_id -> fire count across all sessions
    total_edges: int
    covered_edges: int
    sessions: list[SessionRecord]
    started_at: str
    ended_at: str | None = None
    error: str | None = None
