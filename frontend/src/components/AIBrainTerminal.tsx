import React from 'react';
import { useStore } from '../store';
import { BrainCircuit, AlertTriangle, CheckCircle2, Shield, Rocket, TrendingUp, MessageSquareText } from 'lucide-react';

type DisplayLog = {
    id: string;
    title: string;
    detail: string;
    timestamp: string;
    tone: 'neutral' | 'good' | 'warn' | 'risk' | 'exec' | 'llm';
    content?: string;
};

const toDisplayLog = (log: any): DisplayLog | null => {
    const data = log?.data || {};

    if (log.type === 'decision') {
        return {
            id: log.id,
            title: 'Strategy Decision',
            detail: `${data.operation || 'Hold'} · confidence ${data.probability_score ?? '--'}%`,
            timestamp: log.timestamp,
            tone: 'neutral',
        };
    }

    if (log.type === 'plan') {
        const side = data.side || data.operation || '--';
        const entry = Number(data.entry_price);
        const sl = Number(data.stop_loss);
        const tp = Number(data.take_profit);
        return {
            id: log.id,
            title: 'Risk Plan',
            detail: `${side} · entry ${Number.isFinite(entry) ? entry.toFixed(2) : '--'} · SL ${Number.isFinite(sl) ? sl.toFixed(2) : '--'} · TP ${Number.isFinite(tp) ? tp.toFixed(2) : '--'}`,
            timestamp: log.timestamp,
            tone: 'risk',
        };
    }

    if (log.type === 'execution' || log.type === 'monitor') {
        return {
            id: log.id,
            title: 'Execution',
            detail: log.message || 'Order status update',
            timestamp: log.timestamp,
            tone: 'exec',
        };
    }

    if (log.type === 'llm_log') {
        const model = typeof data.model === 'string' ? data.model : 'LLM';
        const reasoning = typeof data.reasoning === 'string' ? data.reasoning.trim() : '';
        const response = typeof data.response === 'string' ? data.response.trim() : '';
        const prompt = typeof data.prompt === 'string' ? data.prompt.trim() : '';
        const driftScore = typeof data.response === 'string'
            ? (data.response.match(/"drift_score"\s*:\s*(\d+(?:\.\d+)?)/)?.[1] ?? '')
            : '';
        const content = response || reasoning || prompt;

        return {
            id: log.id,
            title: 'LLM Output',
            detail: `${model} · ${log.node || 'llm'}${driftScore ? ` · drift ${driftScore}/10` : ''}`,
            timestamp: log.timestamp,
            tone: 'llm',
            content,
        };
    }

    if (log.type === 'risk_summary') {
        return {
            id: log.id,
            title: 'Risk Summary',
            detail: log.message || 'Risk metrics updated',
            timestamp: log.timestamp,
            tone: 'risk',
        };
    }

    if (log.type === 'error' || log.type === 'warning') {
        return {
            id: log.id,
            title: log.type === 'error' ? 'System Error' : 'Warning',
            detail: log.message,
            timestamp: log.timestamp,
            tone: 'warn',
        };
    }

    if (log.type === 'success' || log.type === 'trade' || log.type === 'market_data') {
        return {
            id: log.id,
            title: 'System Event',
            detail: log.message,
            timestamp: log.timestamp,
            tone: 'good',
        };
    }

    return null;
};

const toneStyle: Record<DisplayLog['tone'], string> = {
    neutral: 'border-border/70 bg-muted/10 text-foreground',
    good: 'border-primary/30 bg-primary/5 text-foreground',
    warn: 'border-destructive/30 bg-destructive/5 text-foreground',
    risk: 'border-amber-500/30 bg-amber-500/5 text-foreground',
    exec: 'border-sky-500/30 bg-sky-500/5 text-foreground',
    llm: 'border-cyan-500/30 bg-cyan-500/5 text-foreground',
};

const toneIcon = (tone: DisplayLog['tone']) => {
    if (tone === 'good') return <CheckCircle2 size={14} className="text-primary" />;
    if (tone === 'warn') return <AlertTriangle size={14} className="text-destructive" />;
    if (tone === 'risk') return <Shield size={14} className="text-amber-400" />;
    if (tone === 'exec') return <Rocket size={14} className="text-sky-400" />;
    if (tone === 'llm') return <MessageSquareText size={14} className="text-cyan-400" />;
    return <TrendingUp size={14} className="text-muted-foreground" />;
};

export const AIBrainTerminal: React.FC<{ className?: string }> = ({ className }) => {
    const logs = useStore((state) => state.logs);
    const analysis = useStore((state) => state.analysis);
    const [showAll, setShowAll] = React.useState(false);

    const displayLogs = React.useMemo(() => {
        const mapped = logs
            .map(toDisplayLog)
            .filter((v): v is DisplayLog => Boolean(v));

        // Drop adjacent duplicates from rapid repeated monitor/status events.
        const deduped: DisplayLog[] = [];
        for (const item of mapped) {
            const prev = deduped[deduped.length - 1];
            if (prev && prev.title === item.title && prev.detail === item.detail) continue;
            deduped.push(item);
        }

        return deduped.slice(0, showAll ? 120 : 40);
    }, [logs, showAll]);

    return (
        <section className={`glass-card p-4 flex flex-col h-full ${className || ''}`}>
            <header className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold tracking-tight flex items-center gap-2">
                    <BrainCircuit size={16} className="text-primary" />
                    AI Execution Log
                </h3>
                <button
                    onClick={() => setShowAll((v) => !v)}
                    className="text-[11px] px-2 py-1 rounded-md border border-border bg-muted/20 text-muted-foreground hover:text-foreground"
                >
                    {showAll ? 'Show Key 40' : 'Show 120'}
                </button>
            </header>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {analysis.drift_score < 5 ? (
                    <article className="border rounded-lg p-2.5 border-destructive/40 bg-destructive/10 text-foreground">
                        <div className="flex items-center gap-2">
                            <AlertTriangle size={14} className="text-destructive" />
                            <span className="text-[11px] font-semibold">Context Drift Alert</span>
                        </div>
                        <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed">
                            drift {analysis.drift_score.toFixed(1)}/10 · changed: {analysis.changed_fields.length ? analysis.changed_fields.join(', ') : 'none'} · Δbuy {analysis.buying_pressure_delta} · Δsell {analysis.selling_pressure_delta}
                        </p>
                    </article>
                ) : null}

                {displayLogs.map((log) => (
                    <article key={log.id} className={`border rounded-lg p-2.5 ${toneStyle[log.tone]}`}>
                        <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                                {toneIcon(log.tone)}
                                <span className="text-[11px] font-semibold">{log.title}</span>
                            </div>
                            <span className="text-[10px] text-muted-foreground">
                                {new Date(log.timestamp).toLocaleTimeString()}
                            </span>
                        </div>
                        <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed">{log.detail}</p>
                        {log.content ? (
                            <details className="mt-2">
                                <summary className="cursor-pointer text-[10px] text-muted-foreground hover:text-foreground">
                                    View LLM Text
                                </summary>
                                <pre className="mt-1.5 whitespace-pre-wrap break-words rounded-md border border-border/70 bg-background/40 p-2 text-[11px] leading-relaxed text-foreground/90">
                                    {log.content}
                                </pre>
                            </details>
                        ) : null}
                    </article>
                ))}

                {displayLogs.length === 0 && (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                        No key execution events yet
                    </div>
                )}
            </div>
        </section>
    );
};
