import React from 'react';
import { PriceChart } from '../components/PriceChart';

export const ChartsView: React.FC = () => {
    return (
        <div className="flex-1 flex flex-col gap-2 min-h-0">
            <div className="flex-1 glass-card p-4 bg-background/50">
                <PriceChart />
            </div>
            <div className="h-1/3 glass-card p-4 overflow-auto">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">Market Context</h3>
                <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 bg-muted/30 rounded-lg border border-border/50">
                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Volatility</span>
                        <span className="text-lg font-mono">2.4% / HR</span>
                    </div>
                    <div className="p-4 bg-muted/30 rounded-lg border border-border/50">
                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Volume (24h)</span>
                        <span className="text-lg font-mono">$42.8B</span>
                    </div>
                    <div className="p-4 bg-muted/30 rounded-lg border border-border/50">
                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">RSI (1h)</span>
                        <span className="text-lg font-mono text-primary">64.2</span>
                    </div>
                </div>
            </div>
        </div>
    );
};
