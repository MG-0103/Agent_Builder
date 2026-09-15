# Design Context

Brief record of the design conversation that shaped this project, so
future sessions (human or agent) can pick up without re-deriving the
reasoning.

## Original problem

Existing agentic system with multiple agents, tools, skills, callback
hooks, and user-defined logic. Asking an LLM to read the codebase and
generate the workflow tree produced plausible but inaccurate output —
LLMs skim, silently guess dynamic dispatch, and can't verify
completeness.

## Ideas discussed

- **LLM-only extraction**: rejected. Symbol-accurate graph
  reconstruction is not what LLMs are reliable at.
- **Dynamic stack-trace capture**: rejected as primary source. Async /
  callback / thread-pool execution mangles parent-child stack
  relationships; the logical `agent → tool` edge often doesn't match
  the trace edge.
- **Structured span instrumentation** (OTel-style): kept as validation
  layer for later (Stage C).
- **Deterministic AST extraction**: chosen as primary. Registrations
  (decorators, constructor kwargs, config files, `.add_node`) are
  declarative; AST resolves them exactly.
- **Graph-first codegen**: considered. Landed on hybrid — parser is
  authoritative now, codegen deferred until parser round-trips
  reliably.

## Scope decisions

- **Framework lock**: Google ADK first. Attempting a generic parser
  before proving one adapter = schema churn. Core schema stays
  framework-neutral; other frameworks plug in as adapters later
  (LangGraph, CrewAI, Claude Agent SDK).
- **Adapter architecture**: plugin-style. Each framework contributes
  its vocabulary of node/edge kinds; core schema is the shared
  contract.

## Layered design

1. **Static extractor** — AST-based, deterministic. Handles the 90%
   case. Records what it can't resolve in `graph.unresolved` and
   degraded parses in `graph.warnings`.
2. **Runtime probe** — subprocess imports target and duck-types
   agents. Handles dynamic tool lists, config-driven wiring,
   cross-file class construction. Merges into static graph;
   name-matched nodes are tagged `meta.observed=true`, new
   findings become `runtime:<name>` nodes with
   `meta.runtime_only=true`.
3. **Trace overlay** *(planned)* — instrument callbacks with OTel
   spans, seed queries against real workflow, diff observed edges
   vs static graph. Edge status: `static_only` (dead code) /
   `observed_only` (parser gap) / `both` (confirmed).

## Non-negotiables

- Graph JSON is the source of truth. Client is a viewer/editor.
- Ids are stable across reparse (no line numbers in ids). Required
  for canvas layout persistence and codegen round-trip.
- Static parser output must be reproducible: same input → same
  graph, deterministic ordering where reasonable.
- LLM involvement stays cosmetic (labels, formatting), never
  extraction.

## What was consciously deferred

- Cross-file class-based construction (kwarg exprs resolve in wrong
  scope). Runtime probe covers.
- MCP toolset live expansion. Needs MCP client dep; runtime probe
  scaffolding is in place for it.
- Codegen round-trip. Waits until parser is trusted end-to-end.
- Canvas polish (typed nodes, edge styles, dagre layout). Next up
  now that parser is stable.

## Session log (this branch)

Commits `9e45a92..2169992` on `main`. Twelve commits: scaffold →
harden tests → graph API → custom subclasses → cross-file base →
attribute chains → shares_state → dynamic tools → class-based
construction → stable ids + warnings + cache → runtime probe →
HTTP endpoints → docs. 55 tests passing.
