import { useMemo } from 'react';

import { useCanvasStore } from '../store/store';

// Shown only when the current graph has trace status metadata on edges.
// Explains the color code — otherwise it's noise.
export function TraceLegend() {
    const edges = useCanvasStore((s) => s.edges);

    const hasStatus = useMemo(
        () =>
            edges.some((e) => {
                const data = e.data as { status?: string } | undefined;
                return typeof data?.status === 'string' && data.status !== 'unknown';
            }),
        [edges],
    );

    if (!hasStatus) return null;

    return (
        <div className="absolute bottom-4 left-4 z-10 rounded-md border bg-white/95 px-3 py-2 text-xs shadow-lg backdrop-blur">
            <div className="mb-1 font-medium text-slate-700">Trace overlay</div>
            <div className="flex flex-col gap-1 text-slate-600">
                <Row color="#059669" label="both — parsed and observed" />
                <Row color="#94a3b8" label="static_only — parsed, not run" dashed />
                <Row color="#ea580c" label="observed_only — ran, parser missed" />
            </div>
        </div>
    );
}

function Row({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
    return (
        <div className="flex items-center gap-2">
            <svg width="20" height="6" aria-hidden>
                <line
                    x1="0"
                    y1="3"
                    x2="20"
                    y2="3"
                    stroke={color}
                    strokeWidth={2}
                    strokeDasharray={dashed ? '3 3' : undefined}
                />
            </svg>
            <span>{label}</span>
        </div>
    );
}
