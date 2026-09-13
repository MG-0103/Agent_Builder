import { Handle, Position } from '@xyflow/react'

import { NodeContextMenu } from './NodeContextMenu'

import { type NodeProps } from '@xyflow/react'


export default function DefaultNode({ id, data }: NodeProps) {
    return (
        <NodeContextMenu
            nodeId={id}
        >
            <div className="rounded-md border bg-white px-4 py-2 shadow">
                <Handle
                    type="target"
                    position={Position.Top}
                />

                <div>
                    {String(data.label)}
                </div>

                <Handle 
                    type="source"
                    position={Position.Bottom}
                />

            </div>
        </NodeContextMenu>
    )
}
