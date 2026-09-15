import { useMemo } from "react"
import {
    getConnectedEdges,
    getIncomers,
    getOutgoers,
} from "@xyflow/react"
import { ExternalLink } from "lucide-react"

import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "../../../ui/accordion";

import {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
} from "../../../ui/card";

import { Separator } from "../../../ui/separator"

import { useCanvasStore } from "../../store/store";

type Provenance = { file: string; line: number; col?: number };

function ProvenanceLink({ provenance }: { provenance?: Provenance }) {
    if (!provenance) return null;
    const { file, line } = provenance;
    const href = `vscode://file/${file}:${line}`;
    const label = `${file.split("/").pop()}:${line}`;
    return (
        <a
            href={href}
            className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline"
            title={`${file}:${line}`}
        >
            <ExternalLink className="h-3 w-3" />
            {label}
        </a>
    );
}

function MetaTable({ meta }: { meta?: Record<string, unknown> }) {
    if (!meta) return null;
    const entries = Object.entries(meta);
    if (entries.length === 0) return null;
    return (
        <div className="space-y-1">
            {entries.map(([k, v]) => (
                <div key={k} className="grid grid-cols-[80px_1fr] gap-2 text-xs">
                    <span className="text-slate-500">{k}</span>
                    <span className="truncate font-mono text-slate-800" title={String(v)}>
                        {typeof v === "string" ? v : JSON.stringify(v)}
                    </span>
                </div>
            ))}
        </div>
    );
}

export function PropertiesPanel() {

    const nodes = useCanvasStore((state) => state.nodes);
    const edges = useCanvasStore((state) => state.edges);

    const selectedNodeId = useCanvasStore(
        (state) => state.selectedNodeId
    );

    const selectedEdgeId = useCanvasStore(
        (state) => state.selectedEdgeId
    );

    const node = nodes.find(
        (node) => node.id === selectedNodeId
    );

    const edge = edges.find(
        (edge) => edge.id === selectedEdgeId
    );

    const connections = useMemo(() => {
        if (!node) return null;

        return {
            incomers: getIncomers(node, nodes, edges),
            outgoers: getOutgoers(node, nodes, edges),
            edges: getConnectedEdges([node], edges),
        };
    }, [node, nodes, edges]);

    if (!node && !edge) {
        return null;
    }

    const title = node ? "Node Properties" : "Edge Properties";
    const data = (node?.data ?? edge?.data) as
        | {
              label?: string;
              kind?: string;
              provenance?: Provenance;
              meta?: Record<string, unknown>;
          }
        | undefined;

    return (
        <Card className="absolute right-4 top-4 z-10 w-80 gap-0 overflow-hidden py-0 shadow-lg">
            <CardHeader className="px-4 py-4">
                <CardTitle className="text-base">
                    {title}
                </CardTitle>
                {data?.label && (
                    <div className="text-xs text-slate-500">
                        {String(data.label)}{" "}
                        {data.kind && <span className="text-slate-400">· {data.kind}</span>}
                    </div>
                )}
            </CardHeader>

            <Separator />

            <CardContent className="p-0">
                <Accordion multiple className="w-full">
                    <AccordionItem value="general" className="border-b">
                        <AccordionTrigger className="px-4 py-3 hover:no-underline">
                            General
                        </AccordionTrigger>
                        <AccordionContent className="px-4 space-y-2">
                            {data?.provenance && (
                                <div>
                                    <div className="mb-1 text-xs text-slate-500">Source</div>
                                    <ProvenanceLink provenance={data.provenance} />
                                </div>
                            )}
                            {node && (
                                <>
                                    <div className="text-xs">Incoming: {connections?.incomers.length}</div>
                                    <div className="text-xs">Outgoing: {connections?.outgoers.length}</div>
                                    <div className="text-xs">Edges: {connections?.edges.length}</div>
                                </>
                            )}
                        </AccordionContent>
                    </AccordionItem>

                    <AccordionItem value="meta" className="border-b">
                        <AccordionTrigger className="px-4 py-3 hover:no-underline">
                            Metadata
                        </AccordionTrigger>
                        <AccordionContent className="px-4">
                            <MetaTable meta={data?.meta} />
                            {(!data?.meta || Object.keys(data.meta).length === 0) && (
                                <div className="text-xs text-slate-400">No metadata.</div>
                            )}
                        </AccordionContent>
                    </AccordionItem>

                    {node && (
                        <AccordionItem value="connections" className="border-b-0">
                            <AccordionTrigger className="px-4 py-3 hover:no-underline">
                                Connections
                            </AccordionTrigger>
                            <AccordionContent className="px-4 space-y-2">
                                {connections?.incomers.length ? (
                                    <div>
                                        <div className="text-xs text-slate-500">Incoming</div>
                                        {connections.incomers.map((n) => (
                                            <div key={n.id} className="text-xs">
                                                ← {String(n.data.label)}
                                            </div>
                                        ))}
                                    </div>
                                ) : null}
                                {connections?.outgoers.length ? (
                                    <div>
                                        <div className="text-xs text-slate-500">Outgoing</div>
                                        {connections.outgoers.map((n) => (
                                            <div key={n.id} className="text-xs">
                                                → {String(n.data.label)}
                                            </div>
                                        ))}
                                    </div>
                                ) : null}
                            </AccordionContent>
                        </AccordionItem>
                    )}
                </Accordion>
            </CardContent>
        </Card>
    );
}
