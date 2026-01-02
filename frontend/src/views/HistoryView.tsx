import React, { useEffect, useState } from 'react';
import { useStore } from '../store';
import { History, Calendar, ChevronRight, Activity, Brain, Shield, Zap, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { TimelineRenderer } from '../components/EventCards';

export const HistoryView: React.FC = () => {
    const { historyRuns, currentRunDetails, historyLoading, fetchHistoryRuns, fetchRunDetails } = useStore();
    const [activeTab, setActiveTab] = useState<'workflows' | 'orders'>('workflows');
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
    const [dateRange, setDateRange] = useState({
        start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end: new Date().toISOString().split('T')[0]
    });

    const [dataSource, setDataSource] = useState<'local' | 'exchange'>('local');
    const [orderHistory, setOrderHistory] = useState<{
        stats: {
            total_trades: number;
            winning_trades: number;
            losing_trades: number;
            total_pnl: number;
            win_rate: number;
        };
        orders: any[];
    } | null>(null);
    const [ordersLoading, setOrdersLoading] = useState(false);

    useEffect(() => {
        if (activeTab === 'workflows') {
            fetchHistoryRuns({
                start_date: `${dateRange.start}T00:00:00Z`,
                end_date: `${dateRange.end}T23:59:59Z`
            });
        } else {
            fetchOrderHistory();
        }
    }, [dateRange, activeTab, dataSource]);

    const fetchOrderHistory = async () => {
        setOrdersLoading(true);
        try {
            const query = new URLSearchParams({
                start_date: `${dateRange.start}T00:00:00Z`,
                end_date: `${dateRange.end}T23:59:59Z`,
                limit: '100',
                source: dataSource
            });
            const url = `http://127.0.0.1:8000/history/orders?${query}`;
            const response = await fetch(url);
            const data = await response.json();
            setOrderHistory(data);
        } catch (e) {
            console.error("Failed to fetch order history", e);
        } finally {
            setOrdersLoading(false);
        }
    };

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
        <div className="flex h-full flex-col gap-4 overflow-hidden">
            {/* Header */}
            <div className="glass-card p-4 rounded-xl flex items-center justify-between shrink-0">
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-3">
                        <History className="text-primary" size={24} />
                        <h2 className="text-xl font-bold tracking-tight">History</h2>
                    </div>

                    {/* Tabs */}
                    <div className="flex bg-muted/50 p-1 rounded-lg border border-border">
                        <button
                            onClick={() => setActiveTab('workflows')}
                            className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all ${activeTab === 'workflows' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                            Workflow Runs
                        </button>
                        <button
                            onClick={() => setActiveTab('orders')}
                            className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all ${activeTab === 'orders' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                            Order History
                        </button>
                    </div>

                    {/* Data Source Toggle (only for orders) */}
                    {activeTab === 'orders' && (
                        <div className="flex bg-muted/30 p-1 rounded-lg border border-border/50 text-[10px] font-bold uppercase">
                            <button
                                onClick={() => setDataSource('local')}
                                className={`px-3 py-1 rounded ${dataSource === 'local' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'}`}
                            >
                                Local DB
                            </button>
                            <button
                                onClick={() => setDataSource('exchange')}
                                className={`px-3 py-1 rounded ${dataSource === 'exchange' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'}`}
                            >
                                Exchange API
                            </button>
                        </div>
                    )}
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

            {/* Content Area */}
            <div className="flex-1 overflow-hidden">
                {activeTab === 'workflows' ? (
                    <WorkflowHistory
                        historyRuns={historyRuns}
                        historyLoading={historyLoading}
                        selectedRunId={selectedRunId}
                        onSelectRun={handleSelectRun}
                        currentRunDetails={currentRunDetails}
                        formatDate={formatDate}
                        StatusBadge={StatusBadge}
                        onCloseDetails={() => setSelectedRunId(null)}
                    />
                ) : (
                    <OrderHistoryContent
                        data={orderHistory}
                        loading={ordersLoading}
                        formatDate={formatDate}
                    />
                )}
            </div>
        </div>
    );
};

// Sub-components to keep clean
const OrderHistoryContent = ({ data, loading, formatDate }: { data: any, loading: boolean, formatDate: (s: string) => string }) => {
    if (loading) return <div className="p-12 text-center animate-pulse text-muted-foreground">Loading orders...</div>;
    if (!data) return <div className="p-12 text-center text-muted-foreground">No data loaded.</div>;

    const { stats, orders } = data;

    return (
        <div className="flex flex-col gap-4 h-full">
            {/* Stats Cards */}
            <div className="grid grid-cols-5 gap-4 shrink-0">
                <StatCard title="Total Trades" value={stats.total_trades} icon={<Activity size={18} className="text-primary" />} />
                <StatCard title="Winning Trades" value={stats.winning_trades} className="text-green-400" icon={<ArrowUpRight size={18} />} />
                <StatCard title="Losing Trades" value={stats.losing_trades} className="text-red-400" icon={<ArrowDownRight size={18} />} />
                <StatCard title="Win Rate" value={`${stats.win_rate.toFixed(1)}%`} icon={<Brain size={18} className="text-accent" />} />
                <StatCard
                    title="Total PnL"
                    value={`$${stats.total_pnl.toFixed(2)}`}
                    className={stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}
                    icon={<Zap size={18} />}
                />
            </div>

            {/* Orders Table */}
            <div className="glass-card rounded-xl flex-1 overflow-hidden flex flex-col">
                <div className="p-4 border-b border-border bg-muted/20 font-bold text-xs uppercase text-muted-foreground grid grid-cols-7 gap-4">
                    <div className="col-span-1">Date</div>
                    <div className="col-span-1">Symbol</div>
                    <div className="col-span-1">Operation</div>
                    <div className="col-span-1 text-right">Price</div>
                    <div className="col-span-1 text-right">Amount</div>
                    <div className="col-span-1 text-right">PnL</div>
                    <div className="col-span-1">Status</div>
                </div>
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    {orders.length === 0 && (
                        <div className="p-8 text-center text-muted-foreground">No orders in this period.</div>
                    )}
                    <div className="divide-y divide-border">
                        {orders.map((order: any) => (
                            <div key={order.id} className="p-4 grid grid-cols-7 gap-4 items-center hover:bg-muted/30 text-sm transition-colors">
                                <div className="col-span-1 text-muted-foreground text-xs">{formatDate(order.createdAt)}</div>
                                <div className="col-span-1 font-bold">{order.symbol}</div>
                                <div className={`col-span-1 font-bold uppercase text-xs px-2 py-1 rounded w-fit ${order.operation === 'Buy' ? 'bg-green-500/20 text-green-400' : order.operation === 'Sell' ? 'bg-red-500/20 text-red-400' : 'bg-muted text-muted-foreground'}`}>
                                    {order.operation}
                                </div>
                                <div className="col-span-1 text-right font-mono">${order.pricing?.toFixed(2) || '--'}</div>
                                <div className="col-span-1 text-right font-mono">{order.amount}</div>
                                <div className={`col-span-1 text-right font-mono font-bold ${order.pnl > 0 ? 'text-green-400' : order.pnl < 0 ? 'text-red-400' : 'text-muted-foreground'}`}>
                                    {order.pnl !== null ? `$${order.pnl.toFixed(2)}` : '--'}
                                </div>
                                <div className="col-span-1">
                                    {order.outcome ? (
                                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${order.outcome === 'profit' ? 'border-green-500/50 text-green-400' : 'border-red-500/50 text-red-400'}`}>
                                            {order.outcome}
                                        </span>
                                    ) : (
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground">Open/Filled</span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}

const StatCard = ({ title, value, icon, className = '' }: { title: string, value: string | number, icon: React.ReactNode, className?: string }) => (
    <div className="glass-card p-4 rounded-xl flex flex-col gap-2">
        <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[10px] uppercase font-bold tracking-wider">{title}</span>
            {icon}
        </div>
        <div className={`text-2xl font-bold tracking-tight ${className}`}>
            {value}
        </div>
    </div>
);

const WorkflowHistory = ({
    historyRuns, historyLoading, selectedRunId, onSelectRun, currentRunDetails, formatDate, StatusBadge, onCloseDetails
}: any) => {
    return (
        <div className="flex h-full gap-4">
            {/* List Side */}
            <div className={`flex flex-col gap-4 ${selectedRunId ? 'w-1/3' : 'w-full'} transition-all duration-300 overflow-hidden`}>
                <div className="glass-card rounded-xl flex-1 overflow-y-auto custom-scrollbar">
                    {historyLoading && <div className="p-8 text-center animate-pulse text-muted-foreground">Loading history...</div>}
                    {!historyLoading && historyRuns.length === 0 && (
                        <div className="p-12 text-center text-muted-foreground">
                            No records found for this period.
                        </div>
                    )}
                    <div className="divide-y divide-border">
                        {historyRuns.map((run: any) => (
                            <div
                                key={run.id}
                                onClick={() => onSelectRun(run.id)}
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
                            <div className="glass-card p-6 rounded-xl relative overflow-hidden shrink-0">
                                <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                                    <Zap size={100} />
                                </div>
                                <div className="flex justify-between items-start mb-6 relative z-10">
                                    <div>
                                        <h3 className="text-2xl font-bold tracking-tighter mb-1">Execution #{currentRunDetails.id.slice(0, 8)}</h3>
                                        <p className="text-sm text-muted-foreground">
                                            {currentRunDetails.symbol} • {currentRunDetails.timeframe}m timeframe • {formatDate(currentRunDetails.created_at)}
                                        </p>
                                    </div>
                                    <button
                                        onClick={onCloseDetails}
                                        className="p-2 hover:bg-muted rounded-lg transition-colors text-muted-foreground relative z-20"
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
                                            <span className="font-bold text-sm">{currentRunDetails.analyses?.length || 0} Nodes</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/40 rounded-lg border border-border/50">
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Executions</span>
                                        <div className="flex items-center gap-2">
                                            <Zap size={14} className="text-primary" />
                                            <span className="font-bold text-sm">{currentRunDetails.executions?.length || 0} Events</span>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-muted/40 rounded-lg border border-border/50">
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Entry Price</span>
                                        <div className="flex items-center gap-2">
                                            {currentRunDetails.observations?.[0] ? (
                                                <span className="font-bold text-sm">${currentRunDetails.observations[0].price.toFixed(2)}</span>
                                            ) : (
                                                <span className="text-muted-foreground">--</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 glass-card rounded-xl flex flex-col overflow-hidden">
                                <div className="p-4 border-b border-border flex gap-4 shrink-0">
                                    <button className="text-sm font-bold text-primary border-b-2 border-primary pb-1">Detailed Timeline</button>
                                </div>
                                <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-4">
                                    <TimelineRenderer
                                        events={[
                                            ...(currentRunDetails.observations || []).map((o: any) => ({ ...o, type: 'observation' })),
                                            ...(currentRunDetails.analyses || []).map((a: any) => ({ ...a, type: 'analysis' })),
                                            ...(currentRunDetails.decisions || []).map((d: any) => ({ ...d, type: 'decision' })),
                                            ...(currentRunDetails.executions || []).map((e: any) => ({ ...e, type: 'execution' })),
                                            ...(currentRunDetails.events || []).map((ev: any) => {
                                                // Preserve timestamp from event, merge data properties
                                                const eventTimestamp = ev.timestamp;
                                                return { ...(ev.data || {}), ...ev, timestamp: eventTimestamp };
                                            }),
                                        ].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())}
                                        formatDate={formatDate}
                                    />
                                </div>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
};

