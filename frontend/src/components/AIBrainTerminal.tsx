/**
 * AI Brain Terminal - Real-time Execution Log Display
 * 
 * Uses shared EventCards components for consistent rendering
 */
import React from 'react';
import { useStore } from '../store';
import { Terminal } from 'lucide-react';
import { EventIcon, LogContent } from './EventCards';

// --- Main Component ---

type LogCategory = 'all' | 'analysis' | 'strategy' | 'execution' | 'error';

export const AIBrainTerminal = () => {
    const logs = useStore((state) => state.logs);
    const [timeFilter, setTimeFilter] = React.useState<number>(0); // 0 = All
    const [categoryFilter, setCategoryFilter] = React.useState<LogCategory>('all');

    const filteredLogs = React.useMemo(() => {
        let result = logs;

        // Category Filter
        if (categoryFilter !== 'all') {
            result = result.filter(log => {
                switch (categoryFilter) {
                    case 'analysis':
                        return ['thinking', 'market_data', 'risk_summary', 'success', 'l0_gate', 'warning'].includes(log.type);
                    case 'strategy':
                        return ['decision', 'plan', 'llm_log'].includes(log.type);
                    case 'execution':
                        return ['execution', 'monitor'].includes(log.type);
                    case 'error':
                        return log.type === 'error';
                    default:
                        return true;
                }
            });
        }

        // Time Filter
        if (timeFilter !== 0) {
            const cutoff = Date.now() - (timeFilter * 60 * 1000);
            result = result.filter(l => {
                const ts = new Date(l.timestamp).getTime();
                return !isNaN(ts) && ts > cutoff;
            });
        }

        return result;
    }, [logs, timeFilter, categoryFilter]);

    return (
        <div className="w-96 glass-card p-4 flex flex-col h-full">
            <div className="flex flex-col gap-3 mb-4 border-b border-border pb-3">
                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                            <Terminal size={16} />
                            AI Execution Log
                        </h3>
                    </div>
                    <span className="text-[10px] font-mono bg-muted/20 px-2 py-0.5 rounded text-muted-foreground">
                        {filteredLogs.length} LOGS
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <select
                        className="flex-1 bg-background/20 border border-border rounded px-2 py-1 text-[10px] focus:outline-none focus:ring-1 focus:ring-primary text-muted-foreground"
                        value={categoryFilter}
                        onChange={(e) => setCategoryFilter(e.target.value as LogCategory)}
                    >
                        <option value="all">ALL CATEGORIES</option>
                        <option value="analysis">ANALYSIS</option>
                        <option value="strategy">STRATEGY</option>
                        <option value="execution">EXECUTION</option>
                        <option value="error">ERRORS</option>
                    </select>

                    <select
                        className="w-24 bg-background/20 border border-border rounded px-2 py-1 text-[10px] focus:outline-none focus:ring-1 focus:ring-primary text-muted-foreground"
                        value={timeFilter}
                        onChange={(e) => setTimeFilter(Number(e.target.value))}
                    >
                        <option value={0}>ALL TIME</option>
                        <option value={5}>LAST 5M</option>
                        <option value={15}>LAST 15M</option>
                        <option value={60}>LAST 1H</option>
                        <option value={1440}>LAST 24H</option>
                    </select>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
                {filteredLogs.map((log) => (
                    <div key={log.id} className="group border-b border-border/30 pb-3 last:border-0 animate-in fade-in slide-in-from-left-2 duration-300">
                        <div className="flex items-center gap-2 mb-1">
                            <EventIcon type={log.type} />
                            <span className="text-[10px] font-mono text-muted-foreground uppercase opacity-70">
                                {new Date(log.timestamp).toLocaleTimeString()} · {log.node}
                            </span>
                        </div>
                        <LogContent log={log} />
                    </div>
                ))}

                {filteredLogs.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center opacity-30 text-center">
                        <Terminal size={48} className="mb-2" />
                        <p className="text-xs uppercase tracking-widest font-bold">Waiting for system tick...</p>
                    </div>
                )}
            </div>
        </div>
    );
};
