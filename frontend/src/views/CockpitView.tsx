import React from 'react';
import { StatsDashboard } from '../components/StatsDashboard';
import { PriceChart } from '../components/PriceChart';
import { GraphView } from '../components/GraphView';
import { AIBrainTerminal } from '../components/AIBrainTerminal';
import { LayoutGrid } from 'lucide-react';

export const CockpitView: React.FC = () => {
    return (
        <>
            <StatsDashboard />
            <div className="flex-1 flex gap-2 min-h-0">
                <div className="flex-1 flex flex-col gap-2 min-w-0">
                    <PriceChart />
                    <div className="h-64 glass-card p-4 flex flex-col">
                        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                            <LayoutGrid size={14} className="text-primary" />
                            LangGraph Execution Topology
                        </h3>
                        <div className="flex-1 min-h-0">
                            <GraphView />
                        </div>
                    </div>
                </div>
                <AIBrainTerminal />
            </div>
        </>
    );
};
