import { useCallback, useRef } from 'react'
import { addEdge, reconnectEdge } from '@xyflow/react'

import { type Connection, type Edge, type Node, type OnSelectionChangeParams } from '@xyflow/react'

import { useCanvasStore } from '../store/store'

export const useCanvasActions = () => {
    const edgeReconnectSuccessful = useRef(false);

    const addNode = useCallback(
        () => {
            const { addNode } = useCanvasStore.getState();

            addNode({
                id: crypto.randomUUID(),
                type: 'default',
                position: {
                    x: 100,
                    y: 100,
                },
                data: {
                    label: 'New Node'
                },
            })
        }, []
    )

    const removeNode = useCallback(
        (id: string) => {
            const { removeNode } = useCanvasStore.getState();

            removeNode(id)
        }, []
    )

    const renameNode = useCallback(
        (id: string, name: string) => {
            const { renameNode } = useCanvasStore.getState();

            renameNode(id, name)
        }, []
    )

    const duplicateNode = useCallback(
        (id: string) => {
            const { nodes, addNode } = useCanvasStore.getState();

            const node = nodes.find((node) => node.id === id)

            if (!node) return;

            addNode({
                ...node, 
                id: crypto.randomUUID(),
                position: {
                    x: node.position.x + 50,
                    y: node.position.y + 50,
                }
            })

        }, []
    )

    const onConnect = useCallback(
        (connection: Connection) => {
            const { edges, setEdges } = useCanvasStore.getState();

            setEdges(addEdge(connection, edges));
        },
        []
    )

    const onReconnectStart = useCallback(() => {
        edgeReconnectSuccessful.current = false;
      }, []);
     
    const onReconnect = useCallback((oldEdge: Edge, newConnection: Connection) => {
        const { edges, setEdges } = useCanvasStore.getState();
        
        edgeReconnectSuccessful.current = true;

        setEdges(reconnectEdge(oldEdge, newConnection, edges));
    }, []);
     
    const onReconnectEnd = useCallback((_: unknown, edge: Edge) => {
        if (!edgeReconnectSuccessful.current) {
            useCanvasStore
                .getState()
                .setEdges((edges) =>
                    edges.filter((e) => e.id !== edge.id)
                );
        }
    
        edgeReconnectSuccessful.current = true;
    }, []);

    const setSelectedNodeId = useCanvasStore(
        (state) => state.setSelectedNodeId
    );

    const setSelectedEdgeId = useCanvasStore(
        (state) => state.setSelectedEdgeId
    );

    const onSelectionChange = useCallback(({ nodes, edges }: OnSelectionChangeParams<Node, Edge>) => {
        if (nodes.length === 1 && edges.length === 0) {
            setSelectedNodeId(nodes[0].id);
            setSelectedEdgeId(null);
            return;
        }
    
        if (edges.length === 1 && nodes.length === 0) {
            setSelectedNodeId(null);
            setSelectedEdgeId(edges[0].id);
            return;
        }
    
        // Nothing selected or multiple selected
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
    }, []);

    return {
        addNode,
        removeNode,
        renameNode,
        duplicateNode,
        onConnect,
        onReconnect,
        onReconnectStart,
        onReconnectEnd,
        onSelectionChange
    }
}