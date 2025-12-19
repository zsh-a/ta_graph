import React from 'react';
import { ShieldAlert } from 'lucide-react';

export const SafetyView: React.FC = () => {
    return (
        <div className="flex-1 flex flex-col gap-4 p-4 overflow-auto">
            <div className="grid grid-cols-3 gap-4">
                <div className="glass-card p-6 border-l-4 border-primary">
                    <h3 className="text-xs font-bold text-muted-foreground uppercase mb-2">Equity Protection</h3>
                    <div className="text-2xl font-bold">ACTIVE</div>
                    <p className="text-xs text-muted-foreground mt-2">Max Drawdown Limit: 5.0%</p>
                </div>
                <div className="glass-card p-6 border-l-4 border-accent">
                    <h3 className="text-xs font-bold text-muted-foreground uppercase mb-2">Compliance Engine</h3>
                    <div className="text-2xl font-bold text-accent">PASSING</div>
                    <p className="text-xs text-muted-foreground mt-2">All pre-trade checks valid</p>
                </div>
                <div className="glass-card p-6 border-l-4 border-destructive">
                    <h3 className="text-xs font-bold text-muted-foreground uppercase mb-2">System Errors</h3>
                    <div className="text-2xl font-bold">0</div>
                    <p className="text-xs text-muted-foreground mt-2">Last 24 hours</p>
                </div>
            </div>
            <div className="flex-1 glass-card p-4">
                <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-2">
                    <ShieldAlert size={16} />
                    System Logs & Security Audit
                </h3>
                <div className="bg-background/50 rounded-lg p-2 font-mono text-xs overflow-auto h-[400px]">
                    <div className="p-2 border-b border-border/50 text-muted-foreground text-[10px]">TIMESTAMP | COMPONENT | ACTION | STATUS</div>
                    {/* Placeholder for raw logs */}
                    <div className="p-2 text-primary/80">[SYSTEM] Initialization complete.</div>
                    <div className="p-2 text-primary/80">[NETWORK] WebSocket established.</div>
                    <div className="p-2 text-accent/80">[RISK] Monitoring active.</div>
                </div>
            </div>
        </div>
    );
};
