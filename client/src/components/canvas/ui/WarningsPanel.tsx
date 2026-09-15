import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';

import { useCanvasStore } from '../store/store';

// Surfaces `graph.warnings` (skipped files, dynamic tools we couldn't
// resolve) and `graph.unresolved` (dangling references) in one panel so
// the user can see what the parser wasn't sure about.
export function WarningsPanel() {
    const warnings = useCanvasStore((s) => s.warnings);
    const unresolved = useCanvasStore((s) => s.unresolved);
    const [open, setOpen] = useState(false);

    const total = warnings.length + unresolved.length;
    if (total === 0) return null;

    return (
        <div className="absolute bottom-16 left-4 z-10 w-96 rounded-md border bg-amber-50 shadow-lg">
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium text-amber-900"
            >
                <span className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Parser issues ({total})
                </span>
                {open ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>

            {open && (
                <div className="max-h-64 overflow-auto border-t border-amber-200 px-3 py-2 text-xs text-amber-950">
                    {warnings.length > 0 && (
                        <>
                            <div className="mb-1 font-semibold">Warnings</div>
                            <ul className="mb-2 space-y-1">
                                {warnings.map((w, i) => (
                                    <li key={`w-${i}`} className="rounded bg-amber-100 px-2 py-1">
                                        <span className="font-mono text-[10px]">
                                            {String(w.kind ?? 'warning')}
                                        </span>
                                        {': '}
                                        {String(w.message ?? JSON.stringify(w))}
                                    </li>
                                ))}
                            </ul>
                        </>
                    )}
                    {unresolved.length > 0 && (
                        <>
                            <div className="mb-1 font-semibold">Unresolved</div>
                            <ul className="space-y-1">
                                {unresolved.map((u, i) => (
                                    <li key={`u-${i}`} className="rounded bg-amber-100 px-2 py-1">
                                        {JSON.stringify(u)}
                                    </li>
                                ))}
                            </ul>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
