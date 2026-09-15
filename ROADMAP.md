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

### Stage C — Trace overlay ✅ (spans + classifier + client styling)
- `adk_parser/trace.py`: `Span` / `Trace` pydantic models; a
  minimal wire format (kind, name, parent_id, attrs) that ADK
  callbacks can emit without an OTel dependency.
- `adk_parser/tracer.py`: `Tracer` helper users drop into their
  ADK code — `wrap_agent_callback`, `wrap_tool_callback`,
  `wrap_named_callback` emit spans with correct parent linkage
  via a contextvar.
- `adk_parser/overlay.py`: `classify(static_graph, trace)` tags
  every static edge with `meta.status`:
  - `both` — parsed and observed
  - `static_only` — parsed but never fired at runtime
  - `observed_only` — trace showed an edge the parser missed
    (added as a new edge + `runtime_only` node).
- `POST /traces` accepts `{repo_path, trace}` and returns the
  classified graph.
- Client edge styling reads `meta.status`: green animated for
  `both`, gray dashed for `static_only`, orange animated for
  `observed_only`. `TraceLegend` renders bottom-left only when
  the graph actually carries status metadata.
- 4 overlay tests + 1 HTTP test.

Still not done:
- Seed-query orchestrator: run inputs, collect spans, iterate
  until coverage plateau.
- Live ADK integration test against a real running project.

### Stage D — Server infra
- File watcher → WebSocket streaming graph deltas on save.
- Schema version negotiation between client and server.
- Structured logging.

### Stage E — Canvas polish ✅
- Typed node components (`AgentNode`, `ToolNode`, `CallbackNode`,
  `AgentAsToolNode`) in `client/src/components/canvas/ui/nodes/TypedNodes.tsx`.
  Color + border per kind, model badge on agents, callback-phase
  badge, `observed` / `runtime-only` tags from probe merge.
- Edge styling by kind in `graphMapper.ts`: `owns_subagent` solid
  navy, `uses_tool` cyan, `wraps_agent` thick violet,
  `hook` dashed amber, `graph_edge` solid black w/ arrow,
  `shares_state` animated dashed green. Kind label rendered on
  each edge.
- Dagre auto-layout (`@dagrejs/dagre`, TB) replacing the row-per-kind
  grid.
- Provenance click-through in PropertiesPanel: `file:line` link
  with `vscode://file/...` href, plus metadata + connections
  accordions and edge-selection support.
- `WarningsPanel`: collapsible list of `graph.warnings` and
  `graph.unresolved`, hidden when empty.
- `LoadRepo` gained an entry-module input feeding through to
  `POST /parse`'s `entry_module` so the runtime probe merge works
  from the UI.
- Pre-existing TS strict-mode errors in `useCanvasActions.ts`
  fixed and `tsconfig.app.json` gets `ignoreDeprecations: "6.0"`
  so `npm run build` passes.

### Stage F — Codegen (round-trip) ✅ (flat emit)
- `adk_parser/codegen.py`: graph → single-file ADK Python emitter.
  Handles llm/sequential/parallel/loop agents, function tools,
  `AgentTool` wrappers, callback fan-in, `sub_agents`, `output_key`,
  and the `Graph()` builder API (add_node/add_edge/
  add_conditional_edges).
- `EmitSkipped` refuses non-round-trippable inputs: custom agent
  subclasses, MCP toolsets, dynamic tool lists, unresolved refs.
- Round-trip parity test (`tests/test_codegen.py`): parse → emit →
  parse yields the same normalized graph on 9 fixtures
  (simple_agent, multi_file, reexport, alias_import, root_absolute,
  attr_chain, state_flow, graph_api, shared_callback). 70 tests
  total pass.
- `POST /emit` HTTP endpoint returns emitted source or 422 on skip.
- `parse-agents ... --emit` CLI flag writes source instead of JSON.

### Stage F polish ✅ (layout emit + regen markers)
- `apply_region(existing, body)` splices a
  `# region agentbuilder:generated` block into an existing file;
  content outside the region is preserved verbatim, and re-emits
  replace exactly one region (idempotent).
- `emit_layout(graph) -> {rel_path: body}` groups nodes by
  `provenance.file`, emits one module per source file, and
  computes cross-file imports (`from pkg.researcher import
  researcher`, etc.) from the graph edges.
- Round-trip parity holds under layout emit on 5 fixtures
  (simple_agent, multi_file, state_flow, shared_callback,
  attr_chain).
- Hand-edit preservation test: a file with hand-written code
  above and below the region survives re-emit unchanged; the
  region itself is replaced in place.
- `POST /emit-layout` returns per-file merged content (or raw
  region bodies via `merge=false`).
- `parse-agents --emit-layout -o <dir>` writes files to disk,
  merging with any existing content via `apply_region`.
- Suite: 82 passed.

Known limitation: tools defined in one module and imported by
another get their `provenance.file` recorded at the *call site*
by the adapter, so layout emit co-locates the function stub with
the referring agent instead of preserving the original `tools.py`.
Round-trip parity still holds (the emitted graph is
self-consistent), but the file layout doesn't perfectly mirror
the input. Fixing this needs a separate `defined_in` field on
tool nodes.

Still not done:
- Codegen for `custom_agent` (needs class-scaffold emission) and
  MCP toolset re-hydration.
- Preserve original tool definition modules.

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

1. **Live trace validation** — run a real ADK repo with the
   `Tracer` wrappers, POST spans to `/traces`, sanity-check the
   overlay classifications end-to-end.
2. **Seed-query orchestrator** — iterate inputs until observed
   edge set plateaus.
3. **Tool provenance fix** — track `defined_in` for
   `tool_function` nodes so layout emit preserves the original
   `tools.py` layout.
4. Stage B tail + Stage D as needed.
