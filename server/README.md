# AgentBuilder Server

Static extractor: Google ADK codebase → workflow graph JSON.

## Setup

```bash
cd server
uv venv
uv pip install -e ".[dev]"
source .venv/bin/activate
```

## Run

CLI:
```bash
parse-agents path/to/adk/project -o graph.json
```

Server:
```bash
uvicorn app:app --reload --port 8000
```

`POST /parse { "repo_path": "..." }` returns Graph JSON.

## Test

```bash
pytest
```

## Status

Phase 2 scaffold. Handles: `LlmAgent`/`Agent`/`SequentialAgent`/`ParallelAgent`/`LoopAgent`, literal `tools=[...]` lists (function refs, `FunctionTool`, `AgentTool`, `MCPToolset`), `sub_agents=[...]`, `*_callback` kwargs.

Not yet: cross-file symbol resolution, ADK graph API (`add_node`/`add_edge`), dynamic tool lists (needs runtime probe), custom `BaseAgent` subclasses, `output_key` data-flow edges.
