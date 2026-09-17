import type { Edge, Node } from '@xyflow/react';
import { MarkerType } from '@xyflow/react';
import dagre from '@dagrejs/dagre';

import type { GraphEdge, GraphNode, ParsedGraph } from './api';

// Trace-status overlay. When /traces has annotated the graph, the runtime
// signal (color, marker, animation) wins over kind styling because it's
// more informative than the parser's kind label — but stroke *patterns*
// (dashed shares_state, hook) are preserved so the kind is still readable.
// Callers merge via `mergeStatus(base, override)` rather than a raw spread.
function statusOverride(status: string | undefined): Partial<Edge> | null {
    switch (status) {
        case 'both':
            return {
                style: { stroke: '#059669', strokeWidth: 2.5 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#059669' },
                animated: true,
            };
        case 'static_only':
            return {
                style: {
                    stroke: '#94a3b8',
                    strokeWidth: 1.2,
                    strokeDasharray: '3 3',
                    opacity: 0.7,
                },
                markerEnd: { type: MarkerType.Arrow, color: '#94a3b8' },
                animated: false,
            };
        case 'observed_only':
            return {
                style: { stroke: '#ea580c', strokeWidth: 2 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#ea580c' },
                animated: true,
            };
        default:
            return null;
    }
}

// Merge kind base with status override, keeping the kind's stroke-dash
// pattern when the override doesn't set one of its own. Prevents e.g. a
// `shares_state` edge with `status=both` from silently losing its dashed
// look and reading as a plain solid edge.
function mergeStatus(base: Partial<Edge>, override: Partial<Edge>): Partial<Edge> {
    const baseStyle = (base.style ?? {}) as Record<string, unknown>;
    const overrideStyle = (override.style ?? {}) as Record<string, unknown>;
    const style = { ...baseStyle, ...overrideStyle };
    if (baseStyle.strokeDasharray && !('strokeDasharray' in overrideStyle)) {
        style.strokeDasharray = baseStyle.strokeDasharray;
    }
    return { ...base, ...override, style };
}

const NODE_W = 220;
const NODE_H = 72;

const AGENT_KINDS = new Set([
    'llm_agent',
    'sequential_agent',
    'parallel_agent',
    'loop_agent',
    'custom_agent',
]);

const TOOL_KINDS = new Set(['tool_function', 'tool_builtin', 'tool_mcp']);

// Map a graph node kind to the React Flow node type we register on the canvas.
export function nodeTypeFor(kind: string): string {
    if (AGENT_KINDS.has(kind)) return 'agent';
    if (kind === 'agent_as_tool') return 'agent_as_tool';
    if (TOOL_KINDS.has(kind)) return 'tool';
    if (kind === 'callback') return 'callback';
    return 'agent';
}

// Style bundle per edge kind. The rendered edge uses `type` + `style` +
// `markerEnd`; `animated` conveys the "state flows through" feel for
// shares_state.
function edgeStyleFor(kind: string): Partial<Edge> {
    switch (kind) {
        case 'owns_subagent':
            return {
                type: 'smoothstep',
                style: { stroke: '#0f172a', strokeWidth: 2 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#0f172a' },
            };
        case 'uses_tool':
            return {
                type: 'smoothstep',
                style: { stroke: '#0891b2', strokeWidth: 1.5 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#0891b2' },
            };
        case 'wraps_agent':
            // Double-line effect: xyflow doesn't ship a double stroke, so we
            // fake it with a thicker outline drawn under a thinner stroke via
            // strokeDasharray. Close enough for a distinguishing look.
            return {
                type: 'smoothstep',
                style: {
                    stroke: '#7c3aed',
                    strokeWidth: 3,
                    strokeDasharray: '0',
                },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#7c3aed' },
            };
        case 'hook':
            return {
                type: 'smoothstep',
                style: {
                    stroke: '#f59e0b',
                    strokeWidth: 1.5,
                    strokeDasharray: '6 4',
                },
                markerEnd: { type: MarkerType.Arrow, color: '#f59e0b' },
            };
        case 'graph_edge':
            return {
                type: 'smoothstep',
                style: { stroke: '#111827', strokeWidth: 2 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#111827' },
            };
        case 'shares_state':
            return {
                type: 'smoothstep',
                animated: true,
                style: {
                    stroke: '#059669',
                    strokeWidth: 1.5,
                    strokeDasharray: '4 3',
                },
                markerEnd: { type: MarkerType.Arrow, color: '#059669' },
            };
        default:
            return {
                type: 'smoothstep',
                style: { stroke: '#94a3b8' },
                markerEnd: { type: MarkerType.Arrow, color: '#94a3b8' },
            };
    }
}

// Dagre layered layout. Direction TB reads well for agent → sub-agents /
// tools; state-flow edges cross layers, which dagre routes around.
function layout(nodes: Node[], edges: Edge[]): Node[] {
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: 'TB', nodesep: 40, ranksep: 80 });

    for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: NODE_H });
    for (const e of edges) g.setEdge(e.source, e.target);

    dagre.layout(g);

    return nodes.map((n) => {
        const p = g.node(n.id);
        return {
            ...n,
            position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 },
        };
    });
}

export function graphToFlow(graph: ParsedGraph): { nodes: Node[]; edges: Edge[] } {
    const rawNodes: Node[] = graph.nodes.map((n: GraphNode) => ({
        id: n.id,
        type: nodeTypeFor(n.kind),
        position: { x: 0, y: 0 },
        data: {
            label: n.name,
            kind: n.kind,
            provenance: n.provenance,
            meta: n.meta ?? {},
        },
    }));

    const nodeIds = new Set(rawNodes.map((n) => n.id));
    const edges: Edge[] = graph.edges
        .filter((e: GraphEdge) => nodeIds.has(e.source) && nodeIds.has(e.target))
        .map((e) => {
            const status = (e.meta as Record<string, unknown> | undefined)?.status as
                | string
                | undefined;
            const override = statusOverride(status);
            const base = edgeStyleFor(e.kind);
            return {
                id: e.id,
                source: e.source,
                target: e.target,
                label: e.kind.replace(/_/g, ' '),
                labelStyle: { fontSize: 10, fill: '#475569' },
                labelBgPadding: [4, 2] as [number, number],
                labelBgBorderRadius: 4,
                labelBgStyle: { fill: '#f8fafc', fillOpacity: 0.9 },
                data: { kind: e.kind, meta: e.meta, status },
                ...(override ? mergeStatus(base, override) : base),
            };
        });

    const nodes = layout(rawNodes, edges);
    return { nodes, edges };
}
