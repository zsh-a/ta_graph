/**
 * Shared Event Card Components
 * 
 * Unified rendering components for timeline events, used by both
 * AIBrainTerminal (real-time) and HistoryView (historical data)
 */
import React from 'react';
import ReactMarkdown from 'react-markdown';
import {
    Activity, Brain, Shield, Zap, Terminal, Cpu, Info,
    AlertTriangle, CheckCircle, TrendingUp, Target, Rocket,
    XCircle, MessageCircle, ArrowUpRight, ArrowDownRight, Fish
} from 'lucide-react';

// ==================== ICON MAPPING ====================

export type EventType =
    | 'thinking' | 'info' | 'error' | 'success' | 'warning'
    | 'decision' | 'plan' | 'execution' | 'monitor'
    | 'llm_log' | 'market_data' | 'risk_summary' | 'trade'
    | 'observation' | 'analysis' | 'l0_gate';

const EVENT_ICON_MAP: Record<EventType, React.ReactNode> = {
    thinking: <Cpu className="text-secondary animate-pulse" size={14} />,
    info: <Info className="text-muted-foreground" size={14} />,
    error: <AlertTriangle className="text-destructive" size={14} />,
    success: <CheckCircle className="text-primary" size={14} />,
    warning: <Fish className="text-yellow-500" size={14} />,
    decision: <TrendingUp className="text-accent" size={14} />,
    plan: <Target className="text-blue-500" size={14} />,
    execution: <Rocket className="text-purple-500" size={14} />,
    monitor: <Activity className="text-orange-500" size={14} />,
    llm_log: <MessageCircle className="text-zinc-400" size={14} />,
    market_data: <Activity className="text-blue-400" size={14} />,
    risk_summary: <Shield className="text-orange-400" size={14} />,
    trade: <Zap className="text-primary" size={14} />,
    observation: <Activity className="text-primary" size={14} />,
    analysis: <Brain className="text-accent" size={14} />,
    l0_gate: <Fish className="text-yellow-500" size={14} />,
};

export const EventIcon = ({ type }: { type: string }) => {
    return EVENT_ICON_MAP[type as EventType] || <Terminal size={14} />;
};

// ==================== SHARED CARD COMPONENTS ====================

export const ThinkingCard = ({ log }: { log: any }) => (
    <div className="flex items-center gap-2">
        <span className="w-1 h-3 bg-secondary rounded-full animate-pulse" />
        {log.message}
    </div>
);

export const DecisionCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-accent/5 border border-accent/20 rounded-md text-[10px] font-mono">
        <div className="flex justify-between">
            <span className="text-accent uppercase">Action: {data.operation}</span>
            <span className="text-muted-foreground">Prob: {data.probability_score}%</span>
        </div>
    </div>
);

export const PlanCard = ({ data }: { data: any }) => (
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

export const ExecutionCard = ({ data }: { data: any }) => (
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
        {data.order_id && (
            <div className="mt-1 text-[8px] text-muted-foreground text-center opacity-50">
                ID: {data.order_id?.substring(0, 12)}...
            </div>
        )}
    </div>
);

export const MonitorCard = ({ data }: { data: any }) => (
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
            <div className="text-muted-foreground mt-1 text-[9px]">{data.reason}</div>
        )}
        {data.message && (
            <div className="text-foreground/80 mt-1">{data.message}</div>
        )}
        {data.fill_price && (
            <div className="flex justify-between mt-2 pt-2 border-t border-border/10">
                <span>Fill: ${data.fill_price}</span>
                <span>Size: {data.size}</span>
            </div>
        )}
    </div>
);

export const MarketDataCard = ({ data }: { data: any }) => (
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
                data.price_change_24h < 0 ? 'text-red-500' : 'text-yellow-500'
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

export const RiskSummaryCard = ({ data }: { data: any }) => (
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
                data.daily_pnl_percent < 0 ? 'text-red-500' : 'text-yellow-500'
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

export const SignalBarCard = ({ data }: { data: any }) => (
    <div className="mt-2 ml-5 p-2 bg-primary/5 border border-primary/20 rounded-md text-[10px] font-mono">
        <div className="flex justify-between items-center mb-2 pb-2 border-b border-primary/10">
            <span className="text-muted-foreground uppercase text-[8px]">Market Cycle</span>
            <span className="text-primary font-bold">{data.market_cycle}</span>
        </div>
        <div className="flex justify-between items-center mb-2">
            <span className="text-muted-foreground uppercase text-[8px]">Always In</span>
            <span className={`font-bold ${data.always_in_direction === 'long' ? 'text-green-500' :
                data.always_in_direction === 'short' ? 'text-red-500' : 'text-yellow-500'
                }`}>
                {data.always_in_direction}
            </span>
        </div>
        <div className="flex justify-between items-center">
            <span className="text-muted-foreground uppercase text-[8px]">Setup Quality</span>
            <span className="text-primary font-bold">{data.setup_quality}/10</span>
        </div>
        {data.signal_bar && (
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
        )}
    </div>
);

export const L0GateCard = ({ data }: { data: any }) => (
    <div className={`mt-2 ml-5 p-2 rounded-md text-[10px] font-mono ${data.is_dead_market
        ? 'bg-yellow-500/5 border border-yellow-500/20'
        : 'bg-green-500/5 border border-green-500/20'
        }`}>
        <div className="flex justify-between items-center">
            <span className="text-muted-foreground uppercase text-[8px]">L0 Gate Result</span>
            <span className={`font-bold ${data.is_dead_market ? 'text-yellow-400' : 'text-green-400'}`}>
                {data.is_dead_market ? '🐟 Dead Market' : '✅ Active Market'}
            </span>
        </div>
        {data.atr_pct !== undefined && (
            <div className="flex justify-between items-center mt-1">
                <span className="text-muted-foreground uppercase text-[8px]">ATR %</span>
                <span className="text-foreground">{data.atr_pct?.toFixed(2)}%</span>
            </div>
        )}
    </div>
);

export const LLMOutputCard = ({ data }: { data: any }) => {
    const [expanded, setExpanded] = React.useState(false);

    return (
        <div className="mt-2 ml-5 p-2 bg-zinc-800/10 border border-zinc-700/50 rounded-md text-[10px] font-mono overflow-hidden">
            <div className="flex justify-between items-center cursor-pointer select-none" onClick={() => setExpanded(!expanded)}>
                <span className="text-zinc-400 font-bold">LLM Interaction ({data.model})</span>
                <span className="text-zinc-500 text-[9px] hover:text-zinc-300 transition-colors">{expanded ? '▲ Hide' : '▼ Show'}</span>
            </div>
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
                            <div className="p-1 text-zinc-400 italic">{data.reasoning}</div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

// ==================== TIMELINE EVENT CARDS (for HistoryView) ====================

interface TimelineEventProps {
    event: any;
    formatDate: (isoStr: string) => string;
}

export const ObservationTimelineCard = ({ event, formatDate }: TimelineEventProps) => (
    <div className="relative pl-8 border-l-2 border-primary/20 pb-4 last:pb-0 group">
        <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-primary rounded-full transition-transform group-hover:scale-110">
            <Activity size={12} className="text-primary" />
        </div>
        <div className="mb-2 flex items-center gap-3">
            <h4 className="font-bold text-xs uppercase tracking-wider text-primary">Market Observation</h4>
            <span className="text-[10px] text-muted-foreground">{formatDate(event.timestamp)}</span>
        </div>
        <div className="p-4 bg-muted/20 hover:bg-muted/30 transition-colors rounded-xl border border-border/50 text-sm">
            <div className="flex gap-8">
                <div>
                    <span className="text-[10px] uppercase text-muted-foreground block font-bold mb-1">Price</span>
                    <span className="font-mono font-bold text-lg">${event.price?.toFixed(2)}</span>
                </div>
                {event.indicators && (
                    <div>
                        <span className="text-[10px] uppercase text-muted-foreground block font-bold mb-1">Indicators</span>
                        <div className="flex gap-4">
                            {event.indicators.rsi && (
                                <div className="flex flex-col">
                                    <span className="text-[9px] text-muted-foreground">RSI</span>
                                    <span className="font-mono font-bold text-accent">{event.indicators.rsi.toFixed(1)}</span>
                                </div>
                            )}
                            {event.indicators.ema20 && (
                                <div className="flex flex-col">
                                    <span className="text-[9px] text-muted-foreground">EMA20</span>
                                    <span className="font-mono font-bold text-primary">${event.indicators.ema20.toFixed(2)}</span>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    </div>
);

export const AnalysisTimelineCard = ({ event, formatDate }: TimelineEventProps) => (
    <div className="relative pl-8 border-l-2 border-accent/20 pb-4 last:pb-0 group">
        <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-accent rounded-full transition-transform group-hover:scale-110">
            <Brain size={12} className="text-accent" />
        </div>
        <div className="mb-2 flex items-center gap-3">
            <h4 className="font-bold text-xs uppercase tracking-wider text-accent">{event.node_name?.replace('_', ' ')}</h4>
            <span className="text-[10px] text-muted-foreground">{formatDate(event.timestamp)}</span>
        </div>
        <div className="p-4 bg-muted/20 hover:bg-muted/30 transition-colors rounded-xl border border-border/50 text-sm">
            <p className="text-muted-foreground mb-3 leading-relaxed">{event.reasoning}</p>
            {event.content?.recommended_action && (
                <div className="flex items-center gap-2 p-2 bg-background/50 rounded-lg border border-border/30 inline-flex">
                    <Info size={14} className="text-primary" />
                    <span className="font-bold uppercase text-[10px]">Recommendation: {event.content.recommended_action}</span>
                </div>
            )}
        </div>
    </div>
);

export const DecisionTimelineCard = ({ event, formatDate }: TimelineEventProps) => (
    <div className="relative pl-8 border-l-2 border-primary/20 pb-4 last:pb-0 group">
        <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-primary rounded-full transition-transform group-hover:scale-110">
            <Shield size={12} className="text-primary" />
        </div>
        <div className="mb-2 flex items-center gap-3">
            <h4 className="font-bold text-xs uppercase tracking-wider text-primary">Strategy Proposal</h4>
            <span className="text-[10px] text-muted-foreground">{formatDate(event.timestamp)}</span>
        </div>
        <div className="p-4 bg-muted/20 hover:bg-muted/30 transition-colors rounded-xl border border-border/50 text-sm">
            <div className="flex items-center gap-6 mb-3">
                <div className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${event.operation === 'Buy' ? 'bg-green-500/20 text-green-400' : event.operation === 'Sell' ? 'bg-red-500/20 text-red-400' : 'bg-muted text-muted-foreground'}`}>
                    {event.operation}
                </div>
                <div className="flex flex-col">
                    <span className="text-[9px] text-muted-foreground uppercase font-bold">Confidence</span>
                    <span className="font-bold text-lg">{((event.probability_score || 0) * 100).toFixed(0)}%</span>
                </div>
                {event.wait_reason && (
                    <div className="flex flex-col">
                        <span className="text-[9px] text-muted-foreground uppercase font-bold">Wait Reason</span>
                        <span className="font-medium text-xs text-orange-400">{event.wait_reason}</span>
                    </div>
                )}
            </div>
            <p className="text-muted-foreground leading-relaxed italic border-l-2 border-primary/30 pl-3">{event.rationale}</p>
        </div>
    </div>
);

export const ExecutionTimelineCard = ({ event, formatDate }: TimelineEventProps) => (
    <div className="relative pl-8 border-l-2 border-primary/20 pb-4 last:pb-0 group">
        <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-primary rounded-full transition-transform group-hover:scale-110">
            <Zap size={12} className="text-primary" />
        </div>
        <div className="mb-2 flex items-center gap-3">
            <h4 className="font-bold text-xs uppercase tracking-wider text-primary">Trade Execution</h4>
            <span className="text-[10px] text-muted-foreground">{formatDate(event.timestamp)}</span>
        </div>
        <div className={`p-4 rounded-xl border flex justify-between items-center transition-colors ${event.status === 'FILLED' ? 'bg-green-500/10 border-green-500/30' : 'bg-muted/20 border-border/50'}`}>
            <div className="flex items-center gap-4">
                <div className={event.side === 'BUY' ? 'text-green-400' : 'text-red-400'}>
                    {event.side === 'BUY' ? <ArrowUpRight size={24} /> : <ArrowDownRight size={24} />}
                </div>
                <div>
                    <span className="block font-bold text-base leading-none mb-1">{event.side} {event.symbol}</span>
                    <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${event.status === 'FILLED' ? 'bg-green-500/20 text-green-400' : 'bg-muted text-muted-foreground'}`}>{event.status}</span>
                </div>
            </div>
            <div className="text-right">
                <span className="block font-mono font-bold text-lg">${event.executed_price?.toFixed(2) || '--'}</span>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">{event.executed_amount || '0'} Units</span>
            </div>
        </div>
    </div>
);

// ==================== UNIFIED LOG CONTENT RENDERER ====================

interface LogContentProps {
    log: {
        type: string;
        message: string;
        data?: any;
    };
}

export const LogContent = ({ log }: LogContentProps) => {
    switch (log.type) {
        case 'thinking':
            return <ThinkingCard log={log} />;
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
        case 'warning':
        case 'l0_gate':
            return <><div className="ml-5 text-yellow-400">{log.message}</div>{log.data && <L0GateCard data={log.data} />}</>;
        case 'success':
            if (log.data?.signal_bar) return <SignalBarCard data={log.data} />;
            return <div className="ml-5 text-muted-foreground/80">{log.message}</div>;
        default:
            return <div className="ml-5 text-muted-foreground/80"><ReactMarkdown>{log.message}</ReactMarkdown></div>;
    }
};

// Generic System Event Card for node_start, l0_gate, etc.
export const SystemEventTimelineCard = ({ event, formatDate }: TimelineEventProps) => {
    // Determine colors and icon based on event type
    const isWarning = event.is_dead_market || event.type === 'l0_gate' && event.is_dead_market;
    const isSuccess = event.type === 'node_complete' || (event.type === 'l0_gate' && !event.is_dead_market);

    const borderColor = isWarning ? 'border-yellow-500/20' : isSuccess ? 'border-green-500/20' : 'border-muted-foreground/20';
    const iconColor = isWarning ? 'border-yellow-500 text-yellow-500' : isSuccess ? 'border-green-500 text-green-500' : 'border-muted-foreground text-muted-foreground';

    // Determine title
    const getTitle = () => {
        switch (event.type) {
            case 'l0_gate': return event.is_dead_market ? '🐟 L0 Gate - Dead Market' : '✅ L0 Gate - Active Market';
            case 'l0_preprocessing_complete': return '📊 L0 Preprocessing Complete';
            case 'node_start': return `🚀 ${event.node || 'Node'} Started`;
            case 'node_complete': return `✓ ${event.node || 'Node'} Complete`;
            case 'market_update': return '📈 Market Update';
            case 'market_data_complete': return '📊 Market Data Complete';
            default: return event.message || event.type;
        }
    };

    return (
        <div className={`relative pl-8 border-l-2 ${borderColor} pb-4 last:pb-0 group`}>
            <div className={`absolute -left-[9px] top-0 p-1 bg-background border-2 ${iconColor} rounded-full transition-transform group-hover:scale-110`}>
                {isWarning ? <Fish size={12} /> : isSuccess ? <CheckCircle size={12} /> : <Activity size={12} />}
            </div>
            <div className="mb-2 flex items-center gap-3">
                <h4 className={`font-bold text-xs uppercase tracking-wider ${isWarning ? 'text-yellow-400' : isSuccess ? 'text-green-400' : 'text-muted-foreground'}`}>
                    {getTitle()}
                </h4>
                <span className="text-[10px] text-muted-foreground">{formatDate(event.timestamp)}</span>
            </div>
            <div className={`p-3 bg-muted/20 hover:bg-muted/30 transition-colors rounded-xl border border-border/50 text-sm`}>
                {event.message && <p className="text-muted-foreground text-xs">{event.message}</p>}
                {event.atr_pct !== undefined && (
                    <div className="flex justify-between items-center mt-2 text-[10px]">
                        <span className="text-muted-foreground uppercase">ATR %</span>
                        <span className="font-mono">{event.atr_pct?.toFixed(2)}%</span>
                    </div>
                )}
                {event.notation_length !== undefined && (
                    <div className="flex justify-between items-center mt-1 text-[10px]">
                        <span className="text-muted-foreground uppercase">Notation Length</span>
                        <span className="font-mono">{event.notation_length} bars</span>
                    </div>
                )}
            </div>
        </div>
    );
};

interface TimelineRendererProps {
    events: any[];
    formatDate: (isoStr: string) => string;
}

export const TimelineRenderer = ({ events, formatDate }: TimelineRendererProps) => {
    if (events.length === 0) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground py-12">
                <Info size={32} className="mb-2 opacity-20" />
                <p>No detailed events recorded for this run.</p>
            </div>
        );
    }

    return (
        <>
            {events.map((event: any, idx: number) => {
                switch (event.type) {
                    case 'observation':
                        return <ObservationTimelineCard key={`obs-${idx}`} event={event} formatDate={formatDate} />;
                    case 'analysis':
                        return <AnalysisTimelineCard key={`ana-${idx}`} event={event} formatDate={formatDate} />;
                    case 'decision':
                        return <DecisionTimelineCard key={`dec-${idx}`} event={event} formatDate={formatDate} />;
                    case 'execution':
                        return <ExecutionTimelineCard key={`exc-${idx}`} event={event} formatDate={formatDate} />;
                    // System events
                    case 'l0_gate':
                    case 'l0_preprocessing_complete':
                    case 'node_start':
                    case 'node_complete':
                    case 'market_update':
                    case 'market_data_complete':
                        return <SystemEventTimelineCard key={`sys-${idx}`} event={event} formatDate={formatDate} />;
                    default:
                        // Fallback for any other event types
                        if (event.message || event.node) {
                            return <SystemEventTimelineCard key={`sys-${idx}`} event={event} formatDate={formatDate} />;
                        }
                        return null;
                }
            })}
        </>
    );
};

