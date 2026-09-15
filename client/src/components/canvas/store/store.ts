// Functional imports
import { create } from "zustand";
import { 
    applyNodeChanges,
    applyEdgeChanges
} from '@xyflow/react';

// Type Imports
import {
    type Node,
    type Edge,
    type OnNodesChange,
    type OnEdgesChange,
} from '@xyflow/react'

import {
    initialNodes, 
    initialEdges
} from "../data/initial-elements";

type GraphIssue = Record<string, unknown>;

type CanvasState = {
    nodes: Node[];
    edges: Edge[];

    warnings: GraphIssue[];
    unresolved: GraphIssue[];

    lastRepoPath: string | null;
    setLastRepoPath: (path: string | null) => void;

    selectedNodeId: string | null;
    selectedEdgeId: string | null;

    setSelectedNodeId: (id: string | null) => void;
    setSelectedEdgeId: (id: string | null) => void;

    onNodesChange: OnNodesChange,
    onEdgesChange: OnEdgesChange,

    addNode: (node: Node) => void;
    removeNode: (id: string) => void;
    renameNode: (id: string, name: string) => void;

    setNodes: (nodes: Node[]) => void;
    setEdges: (edges: Edge[] | ((edges: Edge[]) => Edge[])) => void;
    setIssues: (warnings: GraphIssue[], unresolved: GraphIssue[]) => void;

}


export const useCanvasStore = create<CanvasState>((set) => ({
    nodes: initialNodes,
    edges: initialEdges,

    warnings: [],
    unresolved: [],

    lastRepoPath: null,
    setLastRepoPath: (path) => set({ lastRepoPath: path }),

    selectedNodeId: null,
    selectedEdgeId: null,

    setIssues: (warnings, unresolved) => set({ warnings, unresolved }),

    setSelectedNodeId: (id) =>
        set({ selectedNodeId: id }),
    
    setSelectedEdgeId: (id) =>
        set({ selectedEdgeId: id }),

    setNodes: (nodes) => set({ nodes }),
    setEdges: (edges) =>
        set((state) => ({
            edges: typeof edges === 'function'
                ? edges(state.edges)
                : edges,
        })),

    addNode: (node) =>
        set((state) => ({
            nodes: [...state.nodes, node],
        })),

    removeNode: (id) => set((state) => ({
        nodes: state.nodes.filter((node) => node.id !== id),
        edges: state.edges.filter(
            (edge) => edge.source !== id && edge.target !== id
        )
    })),

    renameNode: (id, name) => set((state) => ({
        nodes: state.nodes.map((node) => 
            node.id === id ? {
                ...node, 
                data: {
                    ...node.data,
                    label: name,
                },
            }
            :node
        )
    })),

    onNodesChange: (changes) => {
        set((state) => ({
            nodes: applyNodeChanges(changes, state.nodes),
        }));
    },

    onEdgesChange: (changes) => {
        set((state) => ({
            edges: applyEdgeChanges(changes, state.edges),
        }));
    },
}));