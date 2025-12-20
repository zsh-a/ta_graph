
import ReactMarkdown from 'react-markdown';
import React from 'react';
import { useStore } from '../store';
import { Terminal, Cpu, Info, AlertTriangle, CheckCircle, TrendingUp, Target, Rocket, Activity, XCircle, MessageCircle } from 'lucide-react';

// --- Sub-Components for Different Log Types ---

const LogIcon = ({ type }: { type: string }) => {
    switch (type) {
        case 'thinking': return <Cpu className="text-secondary animate-pulse" size={14} />;
        case 'info': return <Info className="text-muted-foreground" size={14} />;
        case 'error': return <AlertTriangle className="text-destructive" size={14} />;
        case 'success': return <CheckCircle className="text-primary" size={14} />;
        case 'decision': return <TrendingUp className="text-accent" size={14} />;
        case 'plan': return <Target className="text-blue-500" size={14} />;
        case 'execution': return <Rocket className="text-purple-500" size={14} />;
        case 'monitor': return <Activity className="text-orange-500" size={14} />;
        case 'llm_log': return <MessageCircle className="text-zinc-400" size={14} />;
        default: return <Terminal size={14} />;
    }
};

const ThinkingCard = ({ log }: { log: any }) => (
    <div className="flex items-center gap-2">
        <span className="w-1 h-3 bg-secondary rounded-full animate-pulse" />
        {log.message}
    </div>
);

const DecisionCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-accent/5 border border-accent/20 rounded-md text-[10px] font-mono">
        <div className="flex justify-between">
            <span className="text-accent uppercase">Action: {data.operation}</span>
            <span className="text-muted-foreground">Prob: {data.probability_score}%</span>
        </div>
    </div>
);

const PlanCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-blue-500/5 border border-blue-500/20 rounded-md text-[10px] font-mono">
        <div className="grid grid-cols-2 gap-2 mb-2">
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Action</span>
                <span className={`font-bold ${data.side === 'LONG' ? 'text-green-500' : 'text-red-500'}`}>{data.side}</span>
            </div>
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Symbol</span>
                <span className="font-bold">{data.symbol}</span>
            </div>
        </div>
        <div className="grid grid-cols-3 gap-2 border-t border-border/20 pt-2 mb-2">
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Entry</span>
                <span className="text-foreground">${data.entry_price?.toFixed(2)}</span>
            </div>
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Stop Loss</span>
                <span className="text-red-400">${data.stop_loss?.toFixed(2)}</span>
            </div>
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Take Profit</span>
                <span className="text-green-400">${data.take_profit?.toFixed(2)}</span>
            </div>
        </div>
        <div className="pt-2 border-t border-border/20 flex justify-between">
            <span className="text-muted-foreground">Risk: ${data.risk_amount?.toFixed(2)}</span>
            <span className="text-muted-foreground">Amt: {data.amount?.toFixed(4)}</span>
        </div>
    </div>
);

const ExecutionCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-purple-500/5 border border-purple-500/20 rounded-md text-[10px] font-mono">
        <div className="flex justify-between items-center mb-2">
            <span className={`font-bold px-1.5 py-0.5 rounded text-[9px] ${data.side === 'LONG' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
                {data.side} FILLED
            </span>
            <span className="text-muted-foreground">{data.symbol}</span>
        </div>
        <div className="grid grid-cols-2 gap-2 border-t border-border/20 pt-2">
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Avg Price</span>
                <span className="text-foreground">${data.price?.toFixed(2)}</span>
            </div>
            <div className="flex flex-col text-right">
                <span className="text-muted-foreground uppercase text-[8px]">Amount</span>
                <span className="text-foreground">{data.amount?.toFixed(4)}</span>
            </div>
        </div>
        <div className="mt-1 text-[8px] text-muted-foreground text-center opacity-50">
            ID: {data.order_id?.substring(0, 12)}...
        </div>
    </div>
);

const MonitorCard = ({ data }: { data: any }) => (
    <div className={`mt-2 ml-5 p-2 border rounded-md text-[10px] font-mono ${data.status === 'FILLED' ? 'bg-green-500/5 border-green-500/20' :
        data.status === 'CANCELED' ? 'bg-red-500/5 border-red-500/20' :
            'bg-orange-500/5 border-orange-500/20'
        }`}>
        <div className="flex justify-between items-center mb-1">
            <div className="flex items-center gap-1.5">
                {data.status === 'FILLED' ? <CheckCircle size={10} className="text-green-500" /> :
                    data.status === 'CANCELED' ? <XCircle size={10} className="text-red-500" /> :
                        <Activity size={10} className="text-orange-500" />}
                <span className={`font-bold ${data.status === 'FILLED' ? 'text-green-500' :
                    data.status === 'CANCELED' ? 'text-red-500' : 'text-orange-500'
                    }`}>
                    ORDER {data.status}
                </span>
            </div>
        </div>
        {data.reason && (
            <div className="text-muted-foreground mt-1 text-[9px]">
                {data.reason}
            </div>
        )}
        {data.message && (
            <div className="text-foreground/80 mt-1">
                {data.message}
            </div>
        )}
        {data.fill_price && (
            <div className="flex justify-between mt-2 pt-2 border-t border-border/10">
                <span>Fill: ${data.fill_price}</span>
                <span>Size: {data.size}</span>
            </div>
        )}
    </div>
);

const LLMOutputCard = ({ data }: { data: any }) => {
    const [expanded, setExpanded] = React.useState(false);

    return (
        <div className="mt-2 ml-5 p-2 bg-zinc-800/10 border border-zinc-700/50 rounded-md text-[10px] font-mono overflow-hidden">
            <div className="flex justify-between items-center cursor-pointer select-none" onClick={() => setExpanded(!expanded)}>
                <span className="text-zinc-400 font-bold">LLM Interaction ({data.model})</span>
                <span className="text-zinc-500 text-[9px] hover:text-zinc-300 transition-colors">{expanded ? '▲ Hide' : '▼ Show'}</span>
            </div>

            {/* Always show truncated reasoning or summary if available */}
            {!expanded && data.reasoning && (
                <div className="mt-1 text-zinc-500 line-clamp-2 italic border-l-2 border-zinc-700/50 pl-2">
                    {data.reasoning.substring(0, 100)}...
                </div>
            )}

            {expanded && (
                <div className="mt-2 space-y-2 border-t border-zinc-700/50 pt-2 animate-in fade-in slide-in-from-top-1 duration-200">
                    <div>
                        <span className="text-zinc-500 uppercase text-[8px] block mb-1">User Prompt</span>
                        <div className="bg-black/30 p-2 rounded text-zinc-300 whitespace-pre-wrap max-h-[200px] overflow-y-auto border border-zinc-800/50">
                            {data.prompt}
                        </div>
                    </div>
                    <div>
                        <span className="text-zinc-500 uppercase text-[8px] block mb-1">Response</span>
                        <div className="bg-black/30 p-2 rounded text-green-400/80 whitespace-pre-wrap max-h-[300px] overflow-y-auto font-mono border border-zinc-800/50">
                            {data.response}
                        </div>
                    </div>
                    {data.reasoning && (
                        <div>
                            <span className="text-zinc-500 uppercase text-[8px] block mb-1">Reasoning</span>
                            <div className="p-1 text-zinc-400 italic">
                                {data.reasoning}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

const SignalBarCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-primary/5 border border-primary/20 rounded-md text-[10px] font-mono">
        {/* Market Direction - Most Important */}
        <div className="flex justify-between items-center mb-2 pb-2 border-b border-primary/10">
            <span className="text-muted-foreground uppercase text-[8px]">Market Cycle</span>
            <span className="text-primary font-bold">{data.market_cycle}</span>
        </div>

        {/* Always In Direction */}
        <div className="flex justify-between items-center mb-2">
            <span className="text-muted-foreground uppercase text-[8px]">Always In</span>
            <span className={`font-bold ${data.always_in_direction === 'long' ? 'text-green-500' :
                data.always_in_direction === 'short' ? 'text-red-500' :
                    'text-yellow-500'
                }`}>
                {data.always_in_direction}
            </span>
        </div>

        {/* Setup Quality */}
        <div className="flex justify-between items-center">
            <span className="text-muted-foreground uppercase text-[8px]">Setup Quality</span>
            <span className="text-primary font-bold">{data.setup_quality}/10</span>
        </div>

        {/* Signal Bar Details (Secondary) */}
        <div className="mt-2 pt-2 border-t border-primary/10 text-[9px] opacity-70">
            <div className="flex justify-between">
                <span className="text-muted-foreground">Signal Bar:</span>
                <span className="text-foreground">{data.signal_bar.bar_type}</span>
            </div>
            <div className="flex justify-between">
                <span className="text-muted-foreground">Bar Quality:</span>
                <span className="text-foreground">{data.signal_bar.quality_score}/10</span>
            </div>
        </div>
    </div>
);

const MarketDataCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-blue-500/5 border border-blue-500/20 rounded-md text-[10px] font-mono">
        <div className="flex justify-between items-center mb-2 pb-2 border-b border-blue-500/10">
            <span className="text-muted-foreground uppercase text-[8px]">Symbol</span>
            <span className="text-blue-400 font-bold">{data.symbol} · {data.timeframe}</span>
        </div>

        <div className="flex justify-between items-center mb-1">
            <span className="text-muted-foreground uppercase text-[8px]">Current Price</span>
            <span className="text-foreground font-bold">${data.current_price?.toFixed(2)}</span>
        </div>

        <div className="flex justify-between items-center mb-1">
            <span className="text-muted-foreground uppercase text-[8px]">24h Change</span>
            <span className={`font-bold ${data.price_change_24h > 0 ? 'text-green-500' :
                    data.price_change_24h < 0 ? 'text-red-500' :
                        'text-yellow-500'
                }`}>
                {data.price_change_24h > 0 ? '+' : ''}{data.price_change_24h?.toFixed(2)}%
            </span>
        </div>

        <div className="flex justify-between items-center">
            <span className="text-muted-foreground uppercase text-[8px]">Bars Fetched</span>
            <span className="text-foreground">{data.bars}</span>
        </div>
    </div>
);

const RiskSummaryCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-orange-500/5 border border-orange-500/20 rounded-md text-[10px] font-mono">
        <div className="flex justify-between items-center mb-2 pb-2 border-b border-orange-500/10">
            <span className="text-orange-400 font-bold uppercase text-[8px]">Risk Assessment</span>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-2">
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Available Cash</span>
                <span className="text-foreground font-bold">${data.available_cash?.toFixed(2)}</span>
            </div>
            <div className="flex flex-col">
                <span className="text-muted-foreground uppercase text-[8px]">Total Equity</span>
                <span className="text-foreground font-bold">${data.total_equity?.toFixed(2)}</span>
            </div>
        </div>

        <div className="flex justify-between items-center mb-2">
            <span className="text-muted-foreground uppercase text-[8px]">Daily P&L</span>
            <span className={`font-bold ${data.daily_pnl_percent > 0 ? 'text-green-500' :
                    data.daily_pnl_percent < 0 ? 'text-red-500' :
                        'text-yellow-500'
                }`}>
                {data.daily_pnl_percent > 0 ? '+' : ''}{data.daily_pnl_percent?.toFixed(2)}%
            </span>
        </div>

        <div className="flex justify-between items-center pt-2 border-t border-orange-500/10">
            <span className="text-muted-foreground uppercase text-[8px]">Plans Generated</span>
            <span className="text-orange-400 font-bold">{data.execution_plans}</span>
        </div>
    </div>
);

// --- Component Map ---

const LogContent = ({ log }: { log: any }) => {
    switch (log.type) {
        case 'thinking': return <ThinkingCard log={log} />;
        case 'decision':
            return <><ReactMarkdown>{log.message}</ReactMarkdown><DecisionCard data={log.data} /></>;
        case 'plan':
            return <><ReactMarkdown>{log.message}</ReactMarkdown><PlanCard data={log.data} /></>;
        case 'execution':
            return <><ReactMarkdown>{log.message}</ReactMarkdown><ExecutionCard data={log.data} /></>;
        case 'monitor':
            return <><ReactMarkdown>{log.message}</ReactMarkdown><MonitorCard data={log.data} /></>;
        case 'llm_log':
            return <LLMOutputCard data={log.data} />;
        case 'market_data':
            return <><ReactMarkdown>{log.message}</ReactMarkdown><MarketDataCard data={log.data} /></>;
        case 'risk_summary':
            return <><ReactMarkdown>{log.message}</ReactMarkdown><RiskSummaryCard data={log.data} /></>;
        case 'success':
            if (log.data?.signal_bar) return <SignalBarCard data={log.data} />;
            return <div className="ml-5 text-muted-foreground/80">{log.message}</div>;
        default: return <div className="ml-5 text-muted-foreground/80"><ReactMarkdown>{log.message}</ReactMarkdown></div>;
    }
};

// --- Main Component ---

export const AIBrainTerminal = () => {
    const logs = useStore((state) => state.logs);
    const [timeFilter, setTimeFilter] = React.useState<number>(0); // 0 = All

    const filteredLogs = React.useMemo(() => {
        if (timeFilter === 0) return logs;
        // Simple client-side filtering for now
        const cutoff = Date.now() - (timeFilter * 60 * 1000);
        return logs.filter(l => new Date(l.timestamp).getTime() > cutoff);
    }, [logs, timeFilter]);

    return (
        <div className="w-96 glass-card p-4 flex flex-col h-full">
            <div className="flex justify-between items-center mb-4 border-b border-border pb-2">
                <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        <Terminal size={16} />
                        AI Execution Log
                    </h3>
                </div>

                <div className="flex items-center gap-2">
                    <select
                        className="bg-background/20 border border-border rounded px-2 py-0.5 text-[9px] focus:outline-none focus:ring-1 focus:ring-primary text-muted-foreground"
                        value={timeFilter}
                        onChange={(e) => setTimeFilter(Number(e.target.value))}
                    >
                        <option value={0}>ALL HISTORY</option>
                        <option value={5}>LAST 5M</option>
                        <option value={15}>LAST 15M</option>
                        <option value={60}>LAST 1H</option>
                        <option value={1440}>LAST 24H</option>
                    </select>
                    <span className="text-[10px] font-mono bg-muted/20 px-2 py-0.5 rounded text-muted-foreground">
                        {filteredLogs.length} LOGS
                    </span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
                {filteredLogs.map((log) => (
                    <div key={log.id} className="group border-b border-border/30 pb-3 last:border-0 animate-in fade-in slide-in-from-left-2 duration-300">
                        <div className="flex items-center gap-2 mb-1">
                            <LogIcon type={log.type} />
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
