import React, { useEffect, useMemo } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MarkerType,
    useNodesState,
    useEdgesState,
    Position,
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { useStore } from '../store';

// Subgraph color mapping with better contrast
const SUBGRAPH_COLORS: Record<string, { bg: string; border: string; gradient: string }> = {
    scanner: {
        bg: 'linear-gradient(135deg, #1e3a5f 0%, #2d4a6f 100%)',
        border: '#3b82f6',
        gradient: '#3b82f6'
    },
    manager: {
        bg: 'linear-gradient(135deg, #3d1e5f 0%, #4d2e6f 100%)',
        border: '#8b5cf6',
        gradient: '#8b5cf6'
    },
};

const DEFAULT_NODE_STYLE = {
    background: '#1e293b',
    color: '#f8fafc',
    borderWidth: '2px',
    borderStyle: 'solid' as const,
    borderColor: '#475569',
    borderRadius: '12px',
    padding: '12px 20px',
    fontSize: '13px',
    fontWeight: 600,
    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
    minWidth: '140px',
    textAlign: 'center' as const,
};

const ACTIVE_NODE_STYLE = {
    background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
    boxShadow: '0 0 20px rgba(59, 130, 246, 0.6), 0 4px 12px rgba(0,0,0,0.3)',
    borderColor: '#60a5fa',
    transform: 'scale(1.05)',
};

// Supervisor main flow node style
const SUPERVISOR_NODE_STYLE = {
    ...DEFAULT_NODE_STYLE,
    background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    borderColor: '#64748b',
};

// Pre/Post wrapper node style
const WRAPPER_NODE_STYLE = {
    ...DEFAULT_NODE_STYLE,
    background: '#0f172a',
    borderColor: '#475569',
    borderStyle: 'dashed' as const,
    opacity: 0.8,
    fontSize: '11px',
};

// Static types and options to prevent React Flow warnings
const NODE_TYPES = {};
const EDGE_TYPES = {};
const FIT_VIEW_OPTIONS = { padding: 0.2 };
const DEFAULT_VIEWPORT = { x: 0, y: 0, zoom: 0.8 };

interface GraphNode {
    id: string;
    label: string;
    subgraph?: string;
}

interface GraphEdge {
    source: string;
    target: string;
}

// Improved layout algorithm with hierarchical structure
const calculateNodePositions = (
    nodes: GraphNode[],
    edges: GraphEdge[],
    subgraphs: string[]
): Node[] => {
    const VERTICAL_GAP = 120;
    const SUBGRAPH_HORIZONTAL_GAP = 350;
    const SUBGRAPH_START_X = 400;

    // Categorize nodes
    const mainNodes = nodes.filter(n => !n.subgraph);
    const subgraphNodes: Record<string, GraphNode[]> = {};

    subgraphs.forEach(sg => {
        subgraphNodes[sg] = nodes.filter(n => n.subgraph === sg);
    });

    const result: Node[] = [];

    // Define the main flow order (left column)
    const mainFlowOrder = ['init', 'risk_guard', 'pre_scanner', 'pre_manager', 'post_scanner', 'post_manager', 'cooldown'];

    // Sort main nodes by flow order
    const sortedMainNodes = mainNodes.sort((a, b) => {
        const aIndex = mainFlowOrder.indexOf(a.id);
        const bIndex = mainFlowOrder.indexOf(b.id);
        if (aIndex === -1) return 1;
        if (bIndex === -1) return -1;
        return aIndex - bIndex;
    });

    // Layout main nodes in a vertical flow
    let mainY = 30;
    sortedMainNodes.forEach((node) => {
        const isWrapper = node.id.startsWith('pre_') || node.id.startsWith('post_');

        // Position pre nodes to align with their subgraphs
        let xPos = 50;
        if (node.id === 'pre_scanner' || node.id === 'post_scanner') {
            xPos = 50;
        } else if (node.id === 'pre_manager' || node.id === 'post_manager') {
            xPos = 50;
        }

        result.push({
            id: node.id,
            data: { label: node.label },
            position: { x: xPos, y: mainY },
            sourcePosition: Position.Right,
            targetPosition: Position.Left,
            style: isWrapper ? WRAPPER_NODE_STYLE : SUPERVISOR_NODE_STYLE,
        });

        mainY += VERTICAL_GAP;
    });

    // Layout subgraph nodes vertically, positioned to the right
    let subgraphX = SUBGRAPH_START_X;

    // Sort subgraphs: scanner first, then manager
    const orderedSubgraphs = ['scanner', 'manager'].filter(sg => subgraphs.includes(sg));

    orderedSubgraphs.forEach((subgraph) => {
        const sgNodes = subgraphNodes[subgraph] || [];
        const colors = SUBGRAPH_COLORS[subgraph];

        // Calculate vertical start position logic
        const startY = 50;

        sgNodes.forEach((node, nodeIndex) => {
            // Find if there's an edge coming from the main flow to this subgraph node
            // or if it's strictly internal to the subgraph
            const isInternal = !edges.some(e =>
                (e.source === node.id || e.target === node.id) && !e.source.includes(':')
            );

            result.push({
                id: node.id,
                data: { label: node.label },
                position: {
                    x: subgraphX,
                    y: startY + nodeIndex * VERTICAL_GAP
                },
                // Internal subgraph nodes flow top-to-bottom
                // Entry points from main flow use Left handle for cleaner routing
                sourcePosition: Position.Bottom,
                targetPosition: isInternal ? Position.Top : Position.Left,
                style: {
                    ...DEFAULT_NODE_STYLE,
                    background: colors.bg,
                    borderColor: colors.border,
                    boxShadow: `0 4px 16px ${colors.border}33, 0 2px 8px rgba(0,0,0,0.3)`,
                },
            });
        });

        subgraphX += SUBGRAPH_HORIZONTAL_GAP;
    });

    return result;
};

export const GraphView: React.FC = () => {
    const { graphData, graphLoading, fetchGraphStructure, activeNode } = useStore();

    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    // Fetch graph structure on mount
    useEffect(() => {
        fetchGraphStructure();
    }, [fetchGraphStructure]);

    // Update nodes and edges when graphData changes
    useEffect(() => {
        if (!graphData) return;

        const { nodes: graphNodes, edges: graphEdges, subgraphs } = graphData;

        // Calculate positions for nodes
        const positionedNodes = calculateNodePositions(graphNodes, graphEdges, subgraphs);

        // Convert edges to ReactFlow format with better styling
        const flowEdges: Edge[] = graphEdges.map(edge => {
            const isConditional = edge.conditional;
            const isSubgraphEdge = edge.source.includes(':') || edge.target.includes(':');

            return {
                id: edge.id,
                source: edge.source,
                target: edge.target,
                animated: isSubgraphEdge,
                style: {
                    stroke: isConditional ? '#f59e0b' : (isSubgraphEdge ? '#64748b' : '#475569'),
                    strokeWidth: isConditional ? 2.5 : 2,
                    opacity: 0.8,
                },
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: isConditional ? '#f59e0b' : '#64748b',
                    width: 20,
                    height: 20,
                },
                label: edge.label || undefined,
                labelStyle: {
                    fill: '#e2e8f0',
                    fontSize: 11,
                    fontWeight: 500,
                },
                labelBgStyle: {
                    fill: '#1e293b',
                    fillOpacity: 0.9,
                    rx: 4,
                    ry: 4,
                },
                labelBgPadding: [6, 4] as [number, number],
                type: 'smoothstep',
            };
        });

        setNodes(positionedNodes);
        setEdges(flowEdges);
    }, [graphData, setNodes, setEdges]);

    // Highlight active node
    const displayNodes = useMemo(() => {
        return nodes.map((node) => {
            // Check if this node or its subgraph node is active
            const isActive = node.id === activeNode ||
                node.id.endsWith(`:${activeNode}`) ||
                node.id === `scanner:${activeNode}` ||
                node.id === `manager:${activeNode}`;

            if (isActive) {
                return {
                    ...node,
                    style: {
                        ...node.style,
                        ...ACTIVE_NODE_STYLE,
                    },
                };
            }
            return node;
        });
    }, [nodes, activeNode]);

    if (graphLoading) {
        return (
            <div className="h-full w-full bg-background/50 rounded-xl border border-border flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                    <div className="text-muted-foreground text-sm">Loading graph structure...</div>
                </div>
            </div>
        );
    }

    if (!graphData || graphData.nodes.length === 0) {
        return (
            <div className="h-full w-full bg-background/50 rounded-xl border border-border flex items-center justify-center">
                <div className="text-center text-muted-foreground">
                    <p className="mb-3">No graph data available</p>
                    <button
                        onClick={() => fetchGraphStructure()}
                        className="px-4 py-2 bg-primary/20 hover:bg-primary/30 rounded-lg text-sm transition-colors"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full w-full bg-gradient-to-br from-background/80 to-background/50 rounded-xl border border-border overflow-hidden relative">
            {/* Header */}
            <div className="absolute top-3 left-3 z-10 text-sm font-semibold text-muted-foreground">
                Trading Workflow Graph
            </div>

            {/* Legend */}
            <div className="absolute top-3 right-3 z-10 bg-background/90 backdrop-blur-md rounded-lg p-3 text-xs space-y-2 border border-border/50 shadow-lg">
                <div className="font-semibold text-foreground/80 mb-2">Subgraphs</div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-md" style={{ background: SUBGRAPH_COLORS.scanner.bg, borderColor: SUBGRAPH_COLORS.scanner.border, borderWidth: '1px', borderStyle: 'solid' }}></div>
                    <span className="text-muted-foreground">Scanner (Market Analysis)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-md" style={{ background: SUBGRAPH_COLORS.manager.bg, borderColor: SUBGRAPH_COLORS.manager.border, borderWidth: '1px', borderStyle: 'solid' }}></div>
                    <span className="text-muted-foreground">Manager (Position Mgmt)</span>
                </div>
                <div className="border-t border-border/50 pt-2 mt-2">
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-0.5 rounded" style={{ backgroundColor: '#f59e0b' }}></div>
                        <span className="text-muted-foreground">Conditional</span>
                    </div>
                </div>
            </div>

            <ReactFlow
                nodes={displayNodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={NODE_TYPES}
                edgeTypes={EDGE_TYPES}
                fitView
                fitViewOptions={FIT_VIEW_OPTIONS}
                nodesDraggable={true}
                nodesConnectable={false}
                elementsSelectable={true}
                minZoom={0.3}
                maxZoom={2.5}
                defaultViewport={DEFAULT_VIEWPORT}
            >
                <Background color="#334155" gap={24} size={1} />
                <Controls
                    className="!bg-background/80 !border-border !rounded-lg !shadow-lg"
                    showInteractive={false}
                />
            </ReactFlow>
        </div>
    );
};
