const BASE = import.meta.env.VITE_PARSER_URL ?? 'http://localhost:8000';

export type Provenance = { file: string; line: number; col?: number };

export type GraphNode = {
    id: string;
    kind: string;
    name: string;
    provenance?: Provenance;
    meta?: Record<string, unknown>;
};

export type GraphEdge = {
    id: string;
    source: string;
    target: string;
    kind: string;
    meta?: Record<string, unknown>;
};

export type ParsedGraph = {
    version: string;
    source_root: string;
    framework: string;
    nodes: GraphNode[];
    edges: GraphEdge[];
    unresolved: Array<Record<string, unknown>>;
};

export async function parseRepo(repoPath: string): Promise<ParsedGraph> {
    const res = await fetch(`${BASE}/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath }),
    });
    if (!res.ok) {
        const detail = await res.text();
        throw new Error(`Parse failed (${res.status}): ${detail}`);
    }
    return res.json();
}
