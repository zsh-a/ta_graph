import React from 'react';
import { Brain } from 'lucide-react';
import { GraphView } from '../components/GraphView';
import { AIBrainTerminal } from '../components/AIBrainTerminal';

export const ReasoningView: React.FC = () => {
    return (
        <div className="flex-1 flex gap-2 min-h-0">
            <div className="flex-1 glass-card p-6 flex flex-col overflow-hidden">
                <div className="flex items-center gap-3 mb-6">
                    <Brain className="text-primary" size={24} />
                    <h2 className="text-xl font-bold tracking-tight">AI Reasoning Engine</h2>
                </div>
                <div className="flex-1 min-h-0">
                    <GraphView />
                </div>
            </div>
            <AIBrainTerminal />
        </div>
    );
};
