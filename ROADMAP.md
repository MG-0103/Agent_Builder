# Roadmap

## Done

### Phase 1 — Graph schema
- Framework-neutral `Graph { nodes, edges, warnings, unresolved }` in
  `server/adk_parser/schema.py`.
- Node kinds: `llm_agent`, `sequential_agent`, `parallel_agent`,
  `loop_agent`, `custom_agent`, `tool_function`, `tool_builtin`,
  `tool_mcp`, `agent_as_tool`, `callback`.
- Edge kinds: `owns_subagent`, `uses_tool`, `wraps_agent`, `hook`,
  `graph_edge`, `shares_state`.
- Stable node ids (`<fq_module>:kind:name`, collision counter `#2`).
  Reparse is deterministic.

### Phase 2 — Static extractor (Google ADK)
- Agents: `LlmAgent`, `Agent`, `SequentialAgent`, `ParallelAgent`,
  `LoopAgent`, `BaseAgent`.
- Custom subclasses (transitive): `class X(LlmAgent)`, `class Y(X)`,
  `class Z(BaseAgent)`. Same-file and cross-file base resolution.
- Class-based construction: kwargs from `super().__init__` inside
  `__init__` are merged with the instantiation kwargs (same-module).
- Tools: bare function refs, `FunctionTool`, `AgentTool`,
  `MCPToolset`. Dynamic lists resolved for same-module variable
  assignments, function returns, and `+` concatenation.
- Callbacks: all six `*_agent/model/tool_callback` kwargs. Deduped
  across agents (one node, fan-in edges).
- Sub-agent composition + workflow ordering (`meta.order`).
- ADK graph API: `Graph()/Workflow()/StateGraph()` with
  `.add_node/.add_edge/.add_conditional_edges/.set_entry_point`.
  Conditional routing captured as branch cases in edge meta.
- State-flow: `output_key` producer → `{key}` in downstream
  agent's `instruction` template = `shares_state` edge.
- Cross-file resolver: imports, re-exports (`__init__.py`), aliases
  (`as`), attribute chains (`pkg.mod.symbol`, `import x.y as m`),
  cycle-guarded.
- Warnings channel: `syntax_error` for skipped files,
  `dynamic_tools` for unresolvable tool exprs.

### Phase 3 — Server + client wiring
- FastAPI: `POST /parse`, `POST /probe`, `GET /health`.
- Parse cache keyed by `(root, max_mtime, entry_module)`.
- CORS for Vite dev origin.
- CLI: `parse-agents <path> [-o out.json]`.
- Client: fetch wrapper, `graphToFlow` mapper (naive row-per-kind
  grid layout), `LoadRepo` overlay.

### Phase 4 — Runtime probe
- Subprocess inspector (`adk_parser._inspector`) imports a
  user-specified entry module and walks module-level objects
  duck-typed as agents. No google-adk dependency required in
  target.
- `run_probe(repo, entry_module, timeout)` in
  `adk_parser.probe`.
- `merge_runtime(static_graph, observed)` — name-matches agents,
  tags matched nodes/edges with `meta.observed`, adds
  `runtime:<name>` nodes with `meta.runtime_only` for observations
  the static parser missed. Handles dynamic tool lists.
- `/parse` optional `entry_module` triggers merged result.

### Test suite
55 tests covering agents, tools, callbacks, cross-file resolution
(imports/reexports/aliases/attr-chains/cycles), graph API,
state-flow, custom subclasses, class-based construction, dynamic
tools, malformed sources, CLI, HTTP, and runtime probe.

---

## Not done

### Stage B tail — Runtime probe polish
- Path allowlist for `/parse` and `/probe` (open FS reads today).
- MCP toolset live expansion via MCP client handshake.
- Probe error surfacing on canvas.

### Stage C — Trace overlay (biggest correctness gain)
- OTel-style span emitter auto-wrapping ADK callback hooks
  (`before_agent_callback`, `before_tool_callback`,
  `before_model_callback`).
- `/traces` collector aggregating spans into an observed graph.
- Edge status classification: `static_only` (dead path),
  `observed_only` (parser gap), `both` (confirmed). Rendered as
  edge color/style.
- Seed-query orchestrator: run inputs, collect spans, iterate
  until coverage plateau.

### Stage D — Server infra
- File watcher → WebSocket streaming graph deltas on save.
- Schema version negotiation between client and server.
- Structured logging.

### Stage E — Canvas polish (next up)
- Typed node components: `AgentNode`, `ToolNode`, `CallbackNode`,
  `AgentAsToolNode`. Color + shape per kind, model badge on
  agents.
- Edge styling by kind: solid `owns_subagent`, dashed `hook`,
  double `wraps_agent`, colored labels, arrows for `graph_edge`.
- Auto-layout: swap grid mapper for dagre or elk.
- Provenance click-through: `file:line` → `vscode://` link on
  PropertiesPanel.
- Unresolved / warnings surface panel + canvas badge.
- Entry-module input alongside repo path in `LoadRepo`.

### Stage F — Codegen (round-trip)
- Graph → ADK Python emitter (Jinja templates).
- Regen-safe markers for hand-edited regions.
- Round-trip parity test: parse → emit → parse produces the same
  graph.

### Static extraction gaps (deferred, defensible via runtime probe)
- Cross-file class-based construction (kwarg exprs resolve in the
  class's module scope, not the instantiation site's).
- Attribute base class chains (`class X(pkg.mod.Reviewer)`).
- State reads from tool function bodies (`state["key"]`).
- Comprehensions and mutations after literal init for tool lists.

### Future frameworks
- LangGraph adapter.
- CrewAI adapter.
- Claude Agent SDK adapter.
- AutoGen adapter.

---

## Recommended next order

1. **Stage E — Canvas polish**. Parser is trustworthy; the
   default-node canvas is now the main usability gap.
2. **Stage F — Codegen + round-trip**. Proves parser correctness
   end-to-end; unlocks the graph-as-source-of-truth workflow.
3. **Stage C — Trace overlay**. High value but needs a real
   running ADK repo to trace against; do it once real code lands.
4. Stage B tail + Stage D as needed.
