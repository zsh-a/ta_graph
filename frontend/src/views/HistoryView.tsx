import React, { useEffect, useState } from 'react';
import { useStore } from '../store';
import { History, Calendar, ChevronRight, Activity, Brain, Shield, Zap, Info, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export const HistoryView: React.FC = () => {
    const { historyRuns, currentRunDetails, historyLoading, fetchHistoryRuns, fetchRunDetails } = useStore();
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
    const [dateRange, setDateRange] = useState({
        start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end: new Date().toISOString().split('T')[0]
    });

    useEffect(() => {
        fetchHistoryRuns({
            start_date: `${dateRange.start}T00:00:00Z`,
            end_date: `${dateRange.end}T23:59:59Z`
        });
    }, [dateRange]);

    const handleSelectRun = (runId: string) => {
        setSelectedRunId(runId);
        fetchRunDetails(runId);
    };

    const StatusBadge = ({ status }: { status: string }) => {
        const colors: Record<string, string> = {
            hunting: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
            managing: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
            cooldown: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
            failed: 'bg-red-500/20 text-red-400 border-red-500/50',
            success: 'bg-green-500/20 text-green-400 border-green-500/50',
        };
        const colorClass = colors[status.toLowerCase()] || 'bg-muted text-muted-foreground border-border';

        return (
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${colorClass}`}>
                {status}
            </span>
        );
    };

    const formatDate = (isoStr: string) => {
        return new Date(isoStr).toLocaleString();
    };

    return (
        <div className="flex h-full gap-4 overflow-hidden">
            {/* List Side */}
            <div className={`flex flex-col gap-4 ${selectedRunId ? 'w-1/3' : 'w-full'} transition-all duration-300 overflow-hidden`}>
                <div className="glass-card p-4 rounded-xl flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <History className="text-primary" size={24} />
                        <h2 className="text-xl font-bold tracking-tight">Workflow History</h2>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
                            <input
                                type="date"
                                value={dateRange.start}
                                onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                                className="pl-9 pr-3 py-1.5 bg-muted/50 border border-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                        </div>
                        <span className="text-muted-foreground">to</span>
                        <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
                            <input
                                type="date"
                                value={dateRange.end}
                                onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                                className="pl-9 pr-3 py-1.5 bg-muted/50 border border-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                        </div>
                    </div>
                </div>

                <div className="glass-card rounded-xl flex-1 overflow-y-auto custom-scrollbar">
                    {historyLoading && <div className="p-8 text-center animate-pulse text-muted-foreground">Loading history...</div>}
                    {!historyLoading && historyRuns.length === 0 && (
                        <div className="p-12 text-center text-muted-foreground">
                            No records found for this period.
                        </div>
                    )}
                    <div className="divide-y divide-border">
                        {historyRuns.map((run) => (
                            <div
                                key={run.id}
                                onClick={() => handleSelectRun(run.id)}
                                className={`p-4 hover:bg-muted/30 cursor-pointer transition-all ${selectedRunId === run.id ? 'bg-primary/10 border-l-4 border-primary' : ''}`}
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-sm tracking-tight">{run.symbol}</span>
                                        <span className="text-[10px] text-muted-foreground">{run.timeframe}m</span>
                                    </div>
                                    <StatusBadge status={run.status} />
                                </div>
                                <div className="flex justify-between items-center text-[11px]">
                                    <span className="text-muted-foreground">{formatDate(run.created_at)}</span>
                                    <ChevronRight size={14} className="text-muted-foreground" />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Details Side */}
            {selectedRunId && (
                <div className="flex-1 flex flex-col gap-4 overflow-hidden animate-in slide-in-from-right-4">
                    {!currentRunDetails || historyLoading ? (
                        <div className="glass-card p-8 rounded-xl flex-1 flex flex-col items-center justify-center gap-4">
                            <Activity className="animate-spin text-primary" size={32} />
                            <span className="text-muted-foreground font-medium">Fetching details...</span>
                        </div>
                    ) : (
                        <>
                            <div className="glass-card p-6 rounded-xl relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-4 opacity-10">
                                    <Zap size={100} />
                                </div>
                                <div className="flex justify-between items-start mb-6">
                                    <div>
                                        <h3 className="text-2xl font-bold tracking-tighter mb-1">Execution #{currentRunDetails.id.slice(0, 8)}</h3>
                                        <p className="text-sm text-muted-foreground">
                                            {currentRunDetails.symbol} • {currentRunDetails.timeframe}m timeframe • {formatDate(currentRunDetails.created_at)}
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => setSelectedRunId(null)}
                                        className="p-2 hover:bg-muted rounded-lg transition-colors text-muted-foreground"
                                    >
                                        Close
                                    </button>
                                </div>

                                <div className="grid grid-cols-4 gap-4">
                                    <div className="p-3 bg-muted/40 rounded-lg border border-border/50">
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Status</span>
                                        <div className="flex items-center gap-2">
                                            <Shield size={14} className="text-primary" />
                                            <span className="font-bold text-sm uppercase">{currentRunDetails.status}</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/40 rounded-lg border border-border/50">
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Analyses</span>
                                        <div className="flex items-center gap-2">
                                            <Brain size={14} className="text-accent" />
                                            <span className="font-bold text-sm">{currentRunDetails.analyses.length} Nodes</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/40 rounded-lg border border-border/50">
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Executions</span>
                                        <div className="flex items-center gap-2">
                                            <Zap size={14} className="text-primary" />
                                            <span className="font-bold text-sm">{currentRunDetails.executions.length} Events</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/40 rounded-lg border border-border/50">
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Entry Price</span>
                                        <div className="flex items-center gap-2">
                                            {currentRunDetails.observations[0] ? (
                                                <span className="font-bold text-sm">${currentRunDetails.observations[0].price.toFixed(2)}</span>
                                            ) : (
                                                <span className="text-muted-foreground">--</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 glass-card rounded-xl flex flex-col overflow-hidden">
                                <div className="p-4 border-b border-border flex gap-4">
                                    <button className="text-sm font-bold text-primary border-b-2 border-primary pb-1">Detailed Timeline</button>
                                </div>
                                <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-8">
                                    {/* Observation Step */}
                                    {currentRunDetails.observations.map((obs: any, idx: number) => (
                                        <div key={`obs-${idx}`} className="relative pl-8 border-l-2 border-border/30">
                                            <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-primary rounded-full">
                                                <Activity size={12} className="text-primary" />
                                            </div>
                                            <div className="mb-2 flex items-center gap-3">
                                                <h4 className="font-bold text-sm">Market Observation</h4>
                                                <span className="text-[10px] text-muted-foreground">{formatDate(obs.timestamp)}</span>
                                            </div>
                                            <div className="p-4 bg-muted/30 rounded-xl border border-border/50 text-sm">
                                                <div className="flex gap-8">
                                                    <div>
                                                        <span className="text-[10px] uppercase text-muted-foreground block">Price</span>
                                                        <span className="font-mono font-bold">${obs.price.toFixed(2)}</span>
                                                    </div>
                                                    {obs.indicators && (
                                                        <div>
                                                            <span className="text-[10px] uppercase text-muted-foreground block">RSI</span>
                                                            <span className="font-mono font-bold">{obs.indicators.rsi?.toFixed(1) || '--'}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}

                                    {/* Analysis Step */}
                                    {currentRunDetails.analyses.map((ana: any, idx: number) => (
                                        <div key={`ana-${idx}`} className="relative pl-8 border-l-2 border-border/30">
                                            <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-accent rounded-full">
                                                <Brain size={12} className="text-accent" />
                                            </div>
                                            <div className="mb-2 flex items-center gap-3">
                                                <h4 className="font-bold text-sm uppercase tracking-tight">{ana.node_name.replace('_', ' ')}</h4>
                                                <span className="text-[10px] text-muted-foreground">{formatDate(ana.timestamp)}</span>
                                            </div>
                                            <div className="p-4 bg-muted/30 rounded-xl border border-border/50 text-sm">
                                                <p className="text-muted-foreground mb-3 leading-relaxed">{ana.reasoning}</p>
                                                {ana.content && ana.content.recommended_action && (
                                                    <div className="flex items-center gap-2 p-2 bg-background/50 rounded-lg border border-border/30 inline-flex">
                                                        <Info size={14} className="text-primary" />
                                                        <span className="font-bold uppercase text-[11px]">Recommendation: {ana.content.recommended_action}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}

                                    {/* Decision Step */}
                                    {currentRunDetails.decisions.map((dec: any, idx: number) => (
                                        <div key={`dec-${idx}`} className="relative pl-8 border-l-2 border-border/30">
                                            <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-primary rounded-full">
                                                <Activity size={12} className="text-primary" />
                                            </div>
                                            <div className="mb-2 flex items-center gap-3">
                                                <h4 className="font-bold text-sm">Strategy Proposal</h4>
                                                <span className="text-[10px] text-muted-foreground">{formatDate(dec.timestamp)}</span>
                                            </div>
                                            <div className="p-4 bg-muted/30 rounded-xl border border-border/50 text-sm">
                                                <div className="flex items-center gap-4 mb-3">
                                                    <div className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${dec.operation === 'Buy' ? 'bg-green-500/20 text-green-400' : dec.operation === 'Sell' ? 'bg-red-500/20 text-red-400' : 'bg-muted text-muted-foreground'}`}>
                                                        {dec.operation}
                                                    </div>
                                                    <div className="flex flex-col">
                                                        <span className="text-[10px] text-muted-foreground uppercase font-bold">Confidence</span>
                                                        <span className="font-bold">{(dec.probability_score * 100).toFixed(0)}%</span>
                                                    </div>
                                                </div>
                                                <p className="text-muted-foreground leading-relaxed italic border-l-2 border-primary/30 pl-3">{dec.rationale}</p>
                                            </div>
                                        </div>
                                    ))}

                                    {/* Execution Step */}
                                    {currentRunDetails.executions.map((exc: any, idx: number) => (
                                        <div key={`exc-${idx}`} className="relative pl-8 border-l-2 border-border/30 pb-4">
                                            <div className="absolute -left-[9px] top-0 p-1 bg-background border-2 border-primary rounded-full">
                                                <Zap size={12} className="text-primary" />
                                            </div>
                                            <div className="mb-2 flex items-center gap-3">
                                                <h4 className="font-bold text-sm">Trade Execution</h4>
                                                <span className="text-[10px] text-muted-foreground">{formatDate(exc.timestamp)}</span>
                                            </div>
                                            <div className={`p-4 rounded-xl border flex justify-between items-center ${exc.status === 'FILLED' ? 'bg-green-500/10 border-green-500/30' : 'bg-muted/30 border-border/50'}`}>
                                                <div className="flex items-center gap-4">
                                                    <div className={exc.side === 'BUY' ? 'text-green-400' : 'text-red-400'}>
                                                        {exc.side === 'BUY' ? <ArrowUpRight size={20} /> : <ArrowDownRight size={20} />}
                                                    </div>
                                                    <div>
                                                        <span className="block font-bold leading-none">{exc.side} {exc.symbol}</span>
                                                        <span className="text-[10px] text-muted-foreground uppercase font-bold">{exc.status}</span>
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <span className="block font-mono font-bold">${exc.executed_price?.toFixed(2) || '--'}</span>
                                                    <span className="text-[10px] text-muted-foreground uppercase font-bold">{exc.executed_amount || '0'} Units</span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
};
