import { useEffect, useId, useState } from 'react';

import {
    fetchEntryCandidates,
    parseRepo,
    type EntryCandidate,
} from '../../../lib/api';
import { graphToFlow } from '../../../lib/graphMapper';
import { useCanvasStore } from '../store/store';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';

// Strip surrounding matching quotes users often paste from a shell.
function cleanPath(raw: string): string {
    const s = raw.trim();
    if (s.length >= 2 && s[0] === s[s.length - 1] && (s[0] === '"' || s[0] === "'")) {
        return s.slice(1, -1).trim();
    }
    return s;
}

export function LoadRepo() {
    const [path, setPath] = useState('');
    const [entryModule, setEntryModule] = useState('');
    const [candidates, setCandidates] = useState<EntryCandidate[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const setNodes = useCanvasStore((s) => s.setNodes);
    const setEdges = useCanvasStore((s) => s.setEdges);
    const setIssues = useCanvasStore((s) => s.setIssues);
    const setLastRepoPath = useCanvasStore((s) => s.setLastRepoPath);

    const listId = useId();

    // Debounce candidate lookup while the user is still typing the repo path.
    // 400ms is short enough to feel responsive, long enough that each
    // character doesn't trigger an FS walk on the server.
    useEffect(() => {
        const trimmed = cleanPath(path);
        if (!trimmed) {
            setCandidates([]);
            return;
        }
        const t = setTimeout(async () => {
            const cs = await fetchEntryCandidates(trimmed);
            setCandidates(cs);
        }, 400);
        return () => clearTimeout(t);
    }, [path]);

    const onLoad = async () => {
        const cleaned = cleanPath(path);
        if (!cleaned) return;
        setLoading(true);
        setError(null);
        try {
            const graph = await parseRepo(cleaned, entryModule);
            const { nodes, edges } = graphToFlow(graph);
            setNodes(nodes);
            setEdges(edges);
            setIssues(graph.warnings ?? [], graph.unresolved ?? []);
            setLastRepoPath(cleaned);
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setLoading(false);
        }
    };

    const topPick = candidates[0]?.module;

    return (
        <div className="absolute left-4 top-4 z-10 flex flex-col gap-2 rounded-md bg-background/95 p-3 shadow-lg backdrop-blur">
            <div className="flex items-center gap-2">
                <Input
                    className="w-72"
                    placeholder="/absolute/path/to/adk/project"
                    value={path}
                    onChange={(e) => setPath(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') onLoad();
                    }}
                />
                <Button size="sm" onClick={onLoad} disabled={loading}>
                    {loading ? 'Parsing...' : 'Load'}
                </Button>
            </div>
            <div className="flex flex-col gap-1">
                <Input
                    className="w-72"
                    placeholder={
                        topPick
                            ? `entry module (try ${topPick})`
                            : 'entry module (optional)'
                    }
                    list={listId}
                    value={entryModule}
                    onChange={(e) => setEntryModule(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') onLoad();
                    }}
                />
                <datalist id={listId}>
                    {candidates.map((c) => (
                        <option key={c.module} value={c.module}>
                            {c.agent_count > 0
                                ? `${c.agent_count} agent(s) — ${c.reasons.join(', ')}`
                                : c.reasons.join(', ')}
                        </option>
                    ))}
                </datalist>
                {topPick && !entryModule && (
                    <button
                        type="button"
                        className="w-fit text-[11px] text-indigo-600 hover:underline"
                        onClick={() => setEntryModule(topPick)}
                    >
                        use suggestion: {topPick}
                    </button>
                )}
            </div>
            {error && <div className="text-xs text-red-500">{error}</div>}
        </div>
    );
}
