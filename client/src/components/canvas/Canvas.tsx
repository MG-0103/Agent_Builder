import { useState } from 'react';
import {
    ReactFlow,
    Background,
    Controls,
    ControlButton
} from '@xyflow/react';

import { useCanvasStore } from './store/store';
import { useCanvasActions } from './hooks/useCanvasActions';

import DefaultNode from './ui/nodes/DefaultNode';
import {
    AgentNode,
    ToolNode,
    CallbackNode,
    AgentAsToolNode,
} from './ui/nodes/TypedNodes';
import { PropertiesPanel } from './ui/properties/PropertiesPanel';
import { LoadRepo } from './ui/LoadRepo';
import { WarningsPanel } from './ui/WarningsPanel';
import { TraceLegend } from './ui/TraceLegend';

import { PanelRight, PanelRightClose } from 'lucide-react';
import '@xyflow/react/dist/style.css';


const nodeTypes = {
    default: DefaultNode,
    agent: AgentNode,
    tool: ToolNode,
    callback: CallbackNode,
    agent_as_tool: AgentAsToolNode,
}


export default function Canvas() {
    const nodes = useCanvasStore((state) => state.nodes)
    const edges = useCanvasStore((state) => state.edges)

    const onNodesChange = useCanvasStore(
        (state) => state.onNodesChange
    )
    const onEdgesChange = useCanvasStore(
        (state) => state.onEdgesChange
    )

    const {
        onConnect,
        onReconnect,
        onReconnectStart,
        onReconnectEnd,
        onSelectionChange
    } = useCanvasActions()

    const [showProperties, setShowProperties] = useState(true);

    return (
        <>
            <div className="relative h-full w-full">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    onSelectionChange={onSelectionChange}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onReconnect={onReconnect}
                    onReconnectStart={onReconnectStart}
                    onReconnectEnd={onReconnectEnd}
                >
                    <Controls>
                        <ControlButton
                            className="properties-control"
                            onClick={() => setShowProperties((visible) => !visible)}
                            title={showProperties ? 'Hide properties' : 'Show properties'}
                        >
                            {showProperties ? (
                                <PanelRightClose className="properties-icon" />
                            ) : (
                                <PanelRight className="properties-icon" />
                            )}
                        </ControlButton>
                    </Controls>
                    <Background />
                </ReactFlow>

                <LoadRepo />
                <WarningsPanel />
                <TraceLegend />
                {showProperties && <PropertiesPanel />}
            </div>
        </>
    )
}