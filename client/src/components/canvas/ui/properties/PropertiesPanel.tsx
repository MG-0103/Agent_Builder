import { useMemo } from "react"
import { 
    getConnectedEdges, 
    getIncomers,
    getOutgoers
} from "@xyflow/react"

import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger
} from "../../../ui/accordion";

import {
    Card,
    CardHeader,
    CardTitle,
    CardContent
} from "../../../ui/card";

import { Separator } from "../../../ui/separator"

import { useCanvasStore } from "../../store/store";

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

    return (
        <Card className="absolute right-4 top-4 z-10 w-72 gap-0 overflow-hidden py-0 shadow-lg">
            <CardHeader className="px-4 py-4">
                <CardTitle className="text-base">
                    Node Properties
                </CardTitle>
            </CardHeader>

            <Separator />

            <CardContent className="p-0">
                <Accordion multiple className="w-full">
                    <AccordionItem
                        value="general"
                        className="border-b"
                    >
                        <AccordionTrigger className="px-4 py-3 hover:no-underline">
                            General
                        </AccordionTrigger>
                        <AccordionContent className="px-4">
                            <div>
                                Incoming: {connections?.incomers.length}
                            </div>

                            <div>
                                Outgoing: {connections?.outgoers.length}
                            </div>

                            <div>
                                Edges: {connections?.edges.length}
                            </div>
                            {connections?.incomers.map((node) => (
                                <div key={node.id}>
                                    {String(node.data.label)}
                                </div>
                            ))}
                            </AccordionContent>
                    </AccordionItem>

                    <AccordionItem
                        value="appearance"
                        className="border-b-0"
                    >
                        <AccordionTrigger className="px-4 py-3 hover:no-underline">
                            Appearance
                        </AccordionTrigger>

                        <AccordionContent className="px-4">
                            ...
                        </AccordionContent>
                    </AccordionItem>
                </Accordion>
            </CardContent>
        </Card>
    );
}