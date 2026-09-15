import { useState } from 'react';
import { Activity, ChevronDown, ChevronUp } from 'lucide-react';

import { postTrace } from '../../../lib/api';
import { graphToFlow } from '../../../lib/graphMapper';
import { useCanvasStore } from '../store/store';
import { Button } from '../../ui/button';

// Paste-a-JSON-trace panel. Wants a shape like {"spans": [...]} matching
// adk_parser.trace.Trace. Reuses the last repo path from the LoadRepo box.
export function PostTrace() {
    const [open, setOpen] = useState(false);
    const [raw, setRaw] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const lastRepoPath = useCanvasStore((s) => s.lastRepoPath);
    const setNodes = useCanvasStore((s) => s.setNodes);
    const setEdges = useCanvasStore((s) => s.setEdges);
    const setIssues = useCanvasStore((s) => s.setIssues);

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
        // Accept either a bare Trace object or a wrapped {trace: {...}}.
        const trace =
            typeof parsed === 'object' && parsed && 'spans' in parsed
                ? parsed
                : (parsed as { trace?: unknown }).trace;

        setLoading(true);
        try {
            const graph = await postTrace(lastRepoPath, trace);
            const flow = graphToFlow(graph);
            setNodes(flow.nodes);
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
                onClick={() => setOpen((v) => !v)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium text-slate-700"
            >
                <span className="flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Trace overlay
                </span>
                {open ? (
                    <ChevronDown className="h-4 w-4" />
                ) : (
                    <ChevronUp className="h-4 w-4" />
                )}
            </button>

            {open && (
                <div className="border-t px-3 py-2">
                    <div className="mb-1 text-xs text-slate-500">
                        Paste JSON produced by <code>Tracer.export()</code>.
                    </div>
                    <textarea
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
