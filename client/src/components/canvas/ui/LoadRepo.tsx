import { useState } from 'react';

import { parseRepo } from '../../../lib/api';
import { graphToFlow } from '../../../lib/graphMapper';
import { useCanvasStore } from '../store/store';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';

export function LoadRepo() {
    const [path, setPath] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const setNodes = useCanvasStore((s) => s.setNodes);
    const setEdges = useCanvasStore((s) => s.setEdges);

    const onLoad = async () => {
        if (!path.trim()) return;
        setLoading(true);
        setError(null);
        try {
            const graph = await parseRepo(path.trim());
            const { nodes, edges } = graphToFlow(graph);
            setNodes(nodes);
            setEdges(edges);
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setLoading(false);
        }
    };

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
            {error && <div className="text-xs text-red-500">{error}</div>}
        </div>
    );
}
