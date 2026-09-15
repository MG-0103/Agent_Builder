# AgentBuilder

Reverse-engineer, visualize, and eventually round-trip agentic workflows.

## Problem

Agentic systems mix agents, tools, callbacks, sub-agents, skills, and
user-defined logic across many files. Once a system grows past a couple of
agents, nobody — human or LLM — can reliably reconstruct the full workflow
from the source. Asking an LLM to "read the codebase and draw the tree"
produces plausible-looking but inaccurate graphs: LLMs skim, silently guess
at dynamic dispatch, and can't verify completeness.

## Approach

Deterministic tooling extracts the graph. LLMs are used only for
formatting/labeling at the end, never for symbol-accurate extraction.

Three layers, each independently useful:

1. **Static extractor** — AST-based parser for a specific agent framework
   (currently Google ADK). Emits a framework-neutral graph JSON: agents,
   tools, callbacks, sub-agent composition, graph-API workflows, state-flow
   edges. Cross-file symbol resolution handles imports, re-exports,
   aliases, attribute chains, and custom class hierarchies.
2. **Runtime probe** — spawns a subprocess, imports the target module,
   duck-types agent objects and walks their runtime attributes. Catches
   what static can't see: dynamic tool lists, config-driven wiring,
   MCP toolset expansions, cross-file class-based construction.
3. **Trace overlay** *(planned)* — instruments callback hooks with OTel
   spans, runs happy path + edge case queries, diffs observed edges
   against the static/runtime graph. Static-only edges = dead code;
   runtime-only edges = parser gaps.

The three feed a canvas UI (React + xyflow) where users can inspect the
graph, click through to source (`file:line`), and — eventually — edit
the graph and codegen back to Python.

## Framework scope

Google ADK first. The core schema is framework-neutral; other frameworks
(LangGraph, CrewAI, Claude Agent SDK) plug in as separate adapters that
share the same graph output.

## Repo layout

```
client/    Vite + React + xyflow canvas
server/    FastAPI parser service (Python 3.11+)
  adk_parser/     static AST extractor + runtime probe + merger
  tests/          pytest fixtures + suite
Chats/     Local conversation notes (untracked)
```

## Quickstart

Parser server:
```bash
cd server
uv venv
uv pip install -e ".[dev]"
.venv/bin/uvicorn app:app --reload --port 8000
```

Canvas:
```bash
cd client
npm install
npm run dev
```

Paste a repo path into the canvas Load box (or use the ADK fixture at
`server/tests/fixtures/multi_file`).

## Status

See [ROADMAP.md](ROADMAP.md) for what's done and what's next.
See [CONTEXT.md](CONTEXT.md) for the design decisions behind the
current architecture.
