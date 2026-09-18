"""LLM-driven query generator.

Phase 3 deliverable (single-turn) + Phase 4 extension (multi-turn).
"""
from __future__ import annotations

from typing import Any


def generate_query(
    graph: dict[str, Any],
    target_edge: str | None,
    seed_context: str | None = None,
) -> dict[str, Any]:
    """Phase 3: produce {query, suggested_stubs} given the enriched graph and
    an optional target edge to hit. When target_edge is None the generator
    explores freely, biased toward uncovered edges."""
    raise NotImplementedError("Phase 3 — see auto_probe/__init__.py")


def next_turn(
    graph: dict[str, Any],
    trace_so_far: list[dict[str, Any]],
    session_state: dict[str, Any],
    target_edges_remaining: list[str],
) -> dict[str, Any]:
    """Phase 4: given the trace of the session so far, decide what the user
    would say next to keep progressing toward uncovered edges. Returns
    {next_query} or {end: true, reason: "..."}."""
    raise NotImplementedError("Phase 4 — see auto_probe/__init__.py")
