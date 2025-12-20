import React, { useMemo } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MarkerType,
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { useStore } from '../store';

const initialNodes: Node[] = [
    {
        id: 'market_data',
        data: { label: 'Market Data' },
        position: { x: 250, y: 0 },
        style: {
            background: '#1e293b',
            color: '#f8fafc',
            borderWidth: '1px',
            borderStyle: 'solid',
            borderColor: '#334155'
        }
    },
    {
        id: 'brooks_analyzer',
        data: { label: 'Brooks Analysis' },
        position: { x: 250, y: 100 },
        style: {
            background: '#1e293b',
            color: '#f8fafc',
            borderWidth: '1px',
            borderStyle: 'solid',
            borderColor: '#334155'
        }
    },
    {
        id: 'strategy',
        data: { label: 'Strategy' },
        position: { x: 250, y: 200 },
        style: {
            background: '#1e293b',
            color: '#f8fafc',
            borderWidth: '1px',
            borderStyle: 'solid',
            borderColor: '#334155'
        }
    },
    {
        id: 'risk',
        data: { label: 'Risk Guard' },
        position: { x: 250, y: 300 },
        style: {
            background: '#1e293b',
            color: '#f8fafc',
            borderWidth: '1px',
            borderStyle: 'solid',
            borderColor: '#334155'
        }
    },
    {
        id: 'execution',
        data: { label: 'Execution' },
        position: { x: 250, y: 400 },
        style: {
            background: '#1e293b',
            color: '#f8fafc',
            borderWidth: '1px',
            borderStyle: 'solid',
            borderColor: '#334155'
        }
    },
];

const initialEdges: Edge[] = [
    { id: 'e1-2', source: 'market_data', target: 'brooks_analyzer', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e2-3', source: 'brooks_analyzer', target: 'strategy', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e3-4', source: 'strategy', target: 'risk', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e4-5', source: 'risk', target: 'execution', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
];

export const GraphView: React.FC = () => {
    const activeNode = useStore((state) => state.activeNode);

    const nodes = useMemo(() => {
        return initialNodes.map((node) => {
            if (node.id === activeNode) {
                return {
                    ...node,
                    style: {
                        ...node.style,
                        background: '#3b82f6',
                        boxShadow: '0 0 15px rgba(59, 130, 246, 0.5)',
                        borderColor: '#60a5fa'
                    },
                };
            }
            return node;
        });
    }, [activeNode]);

    return (
        <div className="h-full w-full bg-background/50 rounded-xl border border-border overflow-hidden">
            <ReactFlow
                nodes={nodes}
                edges={initialEdges}
                fitView
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable={false}
            >
                <Background color="#334155" gap={20} />
                <Controls />
            </ReactFlow>
        </div>
    );
};
