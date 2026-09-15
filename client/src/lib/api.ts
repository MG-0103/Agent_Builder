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
    warnings: Array<Record<string, unknown>>;
};

export type EntryCandidate = {
    module: string;
    path: string;
    score: number;
    agent_count: number;
    reasons: string[];
};

export async function fetchEntryCandidates(repoPath: string): Promise<EntryCandidate[]> {
    const res = await fetch(`${BASE}/entry-candidates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath }),
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { candidates: EntryCandidate[] };
    return body.candidates ?? [];
}

export async function postTrace(
    repoPath: string,
    trace: unknown,
): Promise<ParsedGraph> {
    const res = await fetch(`${BASE}/traces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath, trace }),
    });
    if (!res.ok) {
        const detail = await res.text();
        throw new Error(`Trace overlay failed (${res.status}): ${detail}`);
    }
    return res.json();
}

export async function parseRepo(
    repoPath: string,
    entryModule?: string,
): Promise<ParsedGraph> {
    const body: Record<string, unknown> = { repo_path: repoPath };
    if (entryModule && entryModule.trim()) body.entry_module = entryModule.trim();
    const res = await fetch(`${BASE}/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const detail = await res.text();
        throw new Error(`Parse failed (${res.status}): ${detail}`);
    }
    return res.json();
}
