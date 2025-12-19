import React from 'react';
import { StatsDashboard } from '../components/StatsDashboard';

export const PortfolioView: React.FC = () => {
    return (
        <div className="flex-1 flex flex-col gap-4 p-4 overflow-auto">
            <StatsDashboard />
            <div className="grid grid-cols-2 gap-4">
                <div className="glass-card p-6">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-4">Position Distribution</h3>
                    <div className="h-64 flex items-center justify-center border border-dashed border-border rounded-lg">
                        <span className="text-muted-foreground text-sm">Portfolio distribution chart coming soon</span>
                    </div>
                </div>
                <div className="glass-card p-6">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-4">Historical Performance</h3>
                    <div className="h-64 flex items-center justify-center border border-dashed border-border rounded-lg">
                        <span className="text-muted-foreground text-sm">Equity curve chart coming soon</span>
                    </div>
                </div>
            </div>
        </div>
    );
};
