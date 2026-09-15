import { Handle, Position, type NodeProps } from '@xyflow/react';
import { NodeContextMenu } from './NodeContextMenu';

// Kind → human label for the small tag rendered under the node title.
const KIND_LABEL: Record<string, string> = {
    llm_agent: 'LLM Agent',
    sequential_agent: 'Sequential',
    parallel_agent: 'Parallel',
    loop_agent: 'Loop',
    custom_agent: 'Custom',
    tool_function: 'Function',
    tool_builtin: 'Builtin',
    tool_mcp: 'MCP',
    agent_as_tool: 'Agent as Tool',
    callback: 'Callback',
};

type NodeData = {
    label: string;
    kind: string;
    meta?: Record<string, unknown>;
    provenance?: { file: string; line: number };
};

function Shell({
    id,
    data,
    className,
    accent,
    badge,
    footer,
}: {
    id: string;
    data: NodeData;
    className: string;
    accent: string;
    badge?: string;
    footer?: React.ReactNode;
}) {
    const observed = data.meta?.observed === true;
    const runtimeOnly = data.meta?.runtime_only === true;

    return (
        <NodeContextMenu nodeId={id}>
            <div
                className={`min-w-[200px] rounded-md border shadow-sm ${className}`}
            >
                <Handle type="target" position={Position.Top} />

                <div
                    className={`rounded-t-md border-b px-3 py-1 text-[10px] font-semibold uppercase tracking-wide ${accent}`}
                >
                    <div className="flex items-center justify-between gap-2">
                        <span>{KIND_LABEL[data.kind] ?? data.kind}</span>
                        {badge && (
                            <span className="rounded bg-white/60 px-1.5 py-[1px] text-[9px] font-medium normal-case tracking-normal">
                                {badge}
                            </span>
                        )}
                    </div>
                </div>

                <div className="px-3 py-2">
                    <div className="truncate text-sm font-medium text-slate-900">
                        {data.label}
                    </div>
                    {footer}
                    {(observed || runtimeOnly) && (
                        <div className="mt-1 flex gap-1">
                            {observed && (
                                <span className="rounded bg-emerald-100 px-1 py-[1px] text-[9px] text-emerald-700">
                                    observed
                                </span>
                            )}
                            {runtimeOnly && (
                                <span className="rounded bg-amber-100 px-1 py-[1px] text-[9px] text-amber-700">
                                    runtime-only
                                </span>
                            )}
                        </div>
                    )}
                </div>

                <Handle type="source" position={Position.Bottom} />
            </div>
        </NodeContextMenu>
    );
}

export function AgentNode({ id, data }: NodeProps) {
    const d = data as NodeData;
    const model = typeof d.meta?.model === 'string' ? (d.meta.model as string) : undefined;
    return (
        <Shell
            id={id}
            data={d}
            className="bg-white border-indigo-300"
            accent="bg-indigo-50 text-indigo-700"
            badge={model}
        />
    );
}

export function ToolNode({ id, data }: NodeProps) {
    const d = data as NodeData;
    return (
        <Shell
            id={id}
            data={d}
            className="bg-white border-cyan-300 rounded-full"
            accent="bg-cyan-50 text-cyan-700 rounded-t-md"
        />
    );
}

export function CallbackNode({ id, data }: NodeProps) {
    const d = data as NodeData;
    const phase = typeof d.meta?.phase === 'string' ? (d.meta.phase as string) : undefined;
    // "before_agent_callback" → "before agent"
    const shortPhase = phase?.replace(/_callback$/, '').replace(/_/g, ' ');
    return (
        <Shell
            id={id}
            data={d}
            className="bg-white border-amber-300 border-dashed"
            accent="bg-amber-50 text-amber-700"
            badge={shortPhase}
        />
    );
}

export function AgentAsToolNode({ id, data }: NodeProps) {
    const d = data as NodeData;
    return (
        <Shell
            id={id}
            data={d}
            className="bg-white border-violet-400 border-2"
            accent="bg-violet-50 text-violet-700"
        />
    );
}
