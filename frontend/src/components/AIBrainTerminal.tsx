import React from 'react';
import { useStore } from '../store';
import { BrainCircuit, CheckCircle2, AlertTriangle, Shield, Rocket, MessageSquare } from 'lucide-react';

type LogKind = 'all' | 'decision' | 'risk' | 'execution' | 'system';

const isLogKind = (type: string, kind: LogKind) => {
    if (kind === 'all') return true;
    if (kind === 'decision') return type === 'decision' || type === 'llm_log';
    if (kind === 'risk') return type === 'plan' || type === 'risk_summary';
    if (kind === 'execution') return type === 'execution' || type === 'monitor';
    return type === 'warning' || type === 'error' || type === 'success' || type === 'info';
};

const typeIcon = (type: string) => {
    if (type === 'decision' || type === 'llm_log') return <MessageSquare size={14} className="text-sky-400" />;
    if (type === 'plan' || type === 'risk_summary') return <Shield size={14} className="text-amber-400" />;
    if (type === 'execution' || type === 'monitor') return <Rocket size={14} className="text-emerald-400" />;
    if (type === 'warning' || type === 'error') return <AlertTriangle size={14} className="text-orange-400" />;
    return <CheckCircle2 size={14} className="text-zinc-400" />;
};

const compactDetails = (log: any) => {
    const d = log?.data || {};
    if (log.type === 'decision') {
        return `action=${d.operation || 'Hold'} prob=${d.probability_score ?? '--'}`;
    }
    if (log.type === 'plan') {
        return `entry=${d.entry_price ?? '--'} sl=${d.stop_loss ?? '--'} tp=${d.take_profit ?? '--'}`;
    }
    if (log.type === 'execution') {
        return `status=${d.status || '--'} price=${d.price ?? d.executed_price ?? '--'}`;
    }
    if (log.type === 'risk_summary') {
        return `equity=${d.total_equity ?? '--'} cash=${d.available_cash ?? '--'}`;
    }
    return '';
};

export const AIBrainTerminal: React.FC<{ className?: string }> = ({ className }) => {
    const logs = useStore((state) => state.logs);
    const [kind, setKind] = React.useState<LogKind>('all');
    const [limit, setLimit] = React.useState<number>(80);

    const filtered = React.useMemo(
        () => logs.filter((log) => isLogKind(log.type, kind)).slice(0, limit),
        [logs, kind, limit]
    );

    return (
        <section className={`glass-card p-4 flex flex-col h-full ${className || ''}`}>
            <header className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold tracking-tight flex items-center gap-2">
                    <BrainCircuit size={16} className="text-primary" />
                    AI Execution Log
                </h3>
                <span className="text-[11px] text-muted-foreground">{filtered.length} entries</span>
            </header>

            <div className="flex gap-2 mb-3">
                {(['all', 'decision', 'risk', 'execution', 'system'] as LogKind[]).map((k) => (
                    <button
                        key={k}
                        onClick={() => setKind(k)}
                        className={`px-2 py-1 rounded-md text-[11px] capitalize border transition-colors ${
                            kind === k ? 'bg-primary/20 border-primary/40 text-primary' : 'bg-muted/20 border-border text-muted-foreground'
                        }`}
                    >
                        {k}
                    </button>
                ))}
                <select
                    className="ml-auto bg-muted/20 border border-border rounded-md text-[11px] px-2"
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                >
                    <option value={40}>40</option>
                    <option value={80}>80</option>
                    <option value={120}>120</option>
                </select>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {filtered.map((log) => (
                    <article key={log.id} className="border border-border/60 rounded-lg p-2.5 bg-muted/10">
                        <div className="flex items-center justify-between gap-2 mb-1">
                            <div className="flex items-center gap-2">
                                {typeIcon(log.type)}
                                <span className="text-[11px] font-medium">{log.message}</span>
                            </div>
                            <span className="text-[10px] text-muted-foreground">
                                {new Date(log.timestamp).toLocaleTimeString()}
                            </span>
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                            <span>{log.node}</span>
                            {compactDetails(log) ? <span> · {compactDetails(log)}</span> : null}
                        </div>
                    </article>
                ))}

                {filtered.length === 0 && (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                        No actionable logs yet
                    </div>
                )}
            </div>
        </section>
    );
};
