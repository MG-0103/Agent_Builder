import type { Edge, Node } from '@xyflow/react';
import type { GraphEdge, GraphNode, ParsedGraph } from './api';

const COL_W = 260;
const ROW_H = 120;

// ponytail: naive grid layout by kind. Swap for dagre/elk when the graph
// needs collision-free auto-layout.
const KIND_ROW: Record<string, number> = {
    sequential_agent: 0,
    parallel_agent: 0,
    loop_agent: 0,
    llm_agent: 1,
    custom_agent: 1,
    agent_as_tool: 2,
    tool_function: 3,
    tool_builtin: 3,
    tool_mcp: 3,
    callback: 4,
};

function positionFor(node: GraphNode, indexInRow: number): { x: number; y: number } {
    const row = KIND_ROW[node.kind] ?? 5;
    return { x: indexInRow * COL_W, y: row * ROW_H };
}

export function graphToFlow(graph: ParsedGraph): { nodes: Node[]; edges: Edge[] } {
    const rowCounts: Record<number, number> = {};
    const nodes: Node[] = graph.nodes.map((n) => {
        const row = KIND_ROW[n.kind] ?? 5;
        const idx = (rowCounts[row] ??= 0);
        rowCounts[row] = idx + 1;
        return {
            id: n.id,
            type: 'default',
            position: positionFor(n, idx),
            data: {
                label: `${n.name}  (${n.kind})`,
                kind: n.kind,
                provenance: n.provenance,
                meta: n.meta,
            },
        };
    });

    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges: Edge[] = graph.edges
        .filter((e: GraphEdge) => nodeIds.has(e.source) && nodeIds.has(e.target))
        .map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            type: 'smoothstep',
            label: e.kind,
            data: { kind: e.kind, meta: e.meta },
        }));

    return { nodes, edges };
}
