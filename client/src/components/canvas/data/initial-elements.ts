export const initialNodes = [
    {
        id: 'n1',
        position: { x: 0, y: 0 },
        data: { label: 'Node 1' },
        type: 'default',
    },
    {
        id: 'n2',
        position: { x: 250, y: 100 },
        data: { label: 'Node 2' },
        type: 'default',
    },
    {
        id: 'n3',
        position: { x: 500, y: 0 },
        data: { label: 'Node 3' },
        type: 'default',
    },
    {
        id: 'n4',
        position: { x: 250, y: 300 },
        data: { label: 'Node 4' },
        type: 'default',
    },
];

export const initialEdges = [
    {
        id: 'n1-n2',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
        label: 'connects with',
    },
    {
        id: 'n2-n3',
        source: 'n2',
        target: 'n3',
        type: 'smoothstep',
        label: 'connects with',
    },
    {
        id: 'n2-n4',
        source: 'n2',
        target: 'n4',
        type: 'smoothstep',
        label: 'connects with',
    },
];