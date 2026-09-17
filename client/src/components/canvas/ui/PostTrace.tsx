import { useState } from 'react';
import { Activity, ChevronDown, ChevronUp } from 'lucide-react';

import { postTrace } from '../../../lib/api';
import { graphToFlow } from '../../../lib/graphMapper';
import { useCanvasStore } from '../store/store';
import { Button } from '../../ui/button';

// Extract a Trace-shaped object from arbitrary parsed JSON. Accepts either
// a bare `{spans: [...]}` or a wrapper `{trace: {spans: [...]}}`. Returns
// null on anything else so the caller can surface a clear error instead of
// sending garbage to the server.
function extractTrace(parsed: unknown): { spans: unknown[] } | null {
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
    const obj = parsed as Record<string, unknown>;
    const candidate =
        Array.isArray(obj.spans)
            ? obj
            : obj.trace && typeof obj.trace === 'object' && !Array.isArray(obj.trace)
              ? (obj.trace as Record<string, unknown>)
              : null;
    if (!candidate || !Array.isArray(candidate.spans)) return null;
    return candidate as { spans: unknown[] };
}

// Paste-a-JSON-trace panel. Wants a shape like {"spans": [...]} matching
// adk_parser.trace.Trace. Reuses the last repo path from the LoadRepo box.
export function PostTrace() {
    const [open, setOpen] = useState(false);
    const [raw, setRaw] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Only lastRepoPath drives this component's render; the setters are
    // stable references from zustand so reading them off getState in the
    // handler avoids re-rendering on every unrelated store change (node
    // drags, edge edits).
    const lastRepoPath = useCanvasStore((s) => s.lastRepoPath);

    const onApply = async () => {
        if (!lastRepoPath) {
            setError('Load a repo first.');
            return;
        }
        setError(null);

        let parsed: unknown;
        try {
            parsed = JSON.parse(raw || '{}');
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
            return;
        }

        const trace = extractTrace(parsed);
        if (!trace) {
            setError('Expected {"spans": [...]} or {"trace": {"spans": [...]}}.');
            return;
        }

        const { setNodes, setEdges, setIssues, nodes: prevNodes } =
            useCanvasStore.getState();

        // Preserve the user's arranged positions across overlay apply.
        // Dagre re-runs inside graphToFlow, but a canvas the user has been
        // rearranging shouldn't jump on trace apply.
        const prevPositions = new Map(prevNodes.map((n) => [n.id, n.position]));

        setLoading(true);
        try {
            const graph = await postTrace(lastRepoPath, trace);
            const flow = graphToFlow(graph);
            const merged = flow.nodes.map((n) => {
                const prev = prevPositions.get(n.id);
                return prev ? { ...n, position: prev } : n;
            });
            setNodes(merged);
            setEdges(flow.edges);
            setIssues(graph.warnings ?? [], graph.unresolved ?? []);
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="absolute right-4 bottom-4 z-10 w-80 rounded-md border bg-white/95 shadow-lg backdrop-blur">
            <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium text-slate-700"
            >
                <span className="flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Trace overlay
                </span>
                {open ? (
                    <ChevronUp className="h-4 w-4" />
                ) : (
                    <ChevronDown className="h-4 w-4" />
                )}
            </button>

            {open && (
                <div className="border-t px-3 py-2">
                    <div className="mb-1 text-xs text-slate-500">
                        Paste JSON produced by <code>Tracer.export()</code>.
                    </div>
                    <textarea
                        aria-label="Trace JSON"
                        className="mb-2 h-32 w-full resize-none rounded border bg-white px-2 py-1 font-mono text-[11px]"
                        placeholder='{"spans": [{"id": "a1", "kind": "agent", "name": "researcher"}]}'
                        value={raw}
                        onChange={(e) => setRaw(e.target.value)}
                    />
                    <div className="flex items-center justify-between">
                        <Button size="sm" onClick={onApply} disabled={loading}>
                            {loading ? 'Applying...' : 'Overlay'}
                        </Button>
                        {!lastRepoPath && (
                            <span className="text-[10px] text-slate-400">
                                load a repo first
                            </span>
                        )}
                    </div>
                    {error && (
                        <div className="mt-2 text-[11px] text-red-600">{error}</div>
                    )}
                </div>
            )}
        </div>
    );
}
