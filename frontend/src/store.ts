import { create } from 'zustand';

interface TradeLog {
    id: string;
    type: string;
    node: string;
    message: string;
    timestamp: string;
    data?: any;
}

interface DashboardState {
    status: string;
    system: any;
    trading: any;
    performance: any;
    safety: any;
    logs: TradeLog[];
    activeNode: string | null;
    prices: { time: number; value: number }[];
    currentView: string;

    // History State
    historyRuns: any[];
    currentRunDetails: any | null;
    historyLoading: boolean;

    // Graph Structure State
    graphData: {
        nodes: { id: string; label: string; subgraph?: string }[];
        edges: { id: string; source: string; target: string; conditional: boolean; label?: string }[];
        subgraphs: string[];
    } | null;
    graphLoading: boolean;

    // Actions
    updateFromInitialState: (data: any) => void;
    addLog: (log: Omit<TradeLog, 'id'>) => void;
    setSystemStatus: (status: string) => void;
    updatePosition: (position: any) => void;
    setActiveNode: (node: string | null) => void;
    addPrice: (price: { time: number; value: number }) => void;
    setView: (view: string) => void;
    processEvent: (message: any, isHistory?: boolean) => Partial<DashboardState>;
    fetchHistoryRuns: (filters?: any) => Promise<void>;
    fetchRunDetails: (runId: string) => Promise<void>;
    fetchGraphStructure: () => Promise<void>;
}

export const useStore = create<DashboardState>((set, get) => ({
    status: 'offline',
    system: { heartbeat_count: 0, last_heartbeat: null },
    trading: {
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        total_pnl: 0,
        pnl_percentage: 0,
        max_drawdown: 0,
        drawdown_percent: 0,
        current_position: null
    },
    performance: { recent_pnl: [], execution_times: [] },
    safety: { equity_protector: {}, error_count: 0, last_error: null },
    logs: [],
    activeNode: null,
    prices: [],
    currentView: 'cockpit',
    historyRuns: [],
    currentRunDetails: null,
    historyLoading: false,
    graphData: null,
    graphLoading: false,

    updateFromInitialState: (data) => set((state) => {
        let accumulatedLogs: TradeLog[] = [];
        let accumulatedPrices: { time: number; value: number }[] = [];

        // Use a temporary state object to track non-log/price changes during replay
        let replayStatus = data.system?.status || state.status;
        let replayActiveNode = state.activeNode;

        if (data.history && Array.isArray(data.history)) {
            // History events are provided from oldest to newest
            data.history.forEach((event: any) => {
                const updates = get().processEvent(event, true);

                if (updates.logs) {
                    // Newest logs should be at the beginning of the list
                    accumulatedLogs = [...updates.logs, ...accumulatedLogs];
                }
                if (updates.prices) {
                    accumulatedPrices = [...accumulatedPrices, ...updates.prices];
                }
                if (updates.activeNode !== undefined) {
                    replayActiveNode = updates.activeNode;
                }
                if (updates.status !== undefined) {
                    replayStatus = updates.status;
                }
            });
        }

        // IMPORTANT: Sort and de-duplicate prices for lightweight-charts
        // Sorting by time (ASC) is required.
        accumulatedPrices.sort((a, b) => a.time - b.time);

        const finalPrices: { time: number; value: number }[] = [];
        const seenTimes = new Set<number>();

        for (const p of accumulatedPrices) {
            // Use a small precision factor or round to avoid floating point issues if any
            const roundedTime = Math.round(p.time * 1000) / 1000;
            if (!seenTimes.has(roundedTime)) {
                finalPrices.push({ ...p, time: roundedTime });
                seenTimes.add(roundedTime);
            }
        }

        return {
            ...state,
            status: replayStatus,
            system: data.system || state.system,
            trading: data.trading || state.trading,
            performance: data.performance || state.performance,
            safety: data.safety || state.safety,
            logs: accumulatedLogs.slice(0, 500),
            prices: finalPrices.slice(-1000),
            activeNode: replayActiveNode
        };
    }),

    processEvent: (message: any, isHistory = false) => {
        const { type, data, timestamp } = message;
        let updates: Partial<DashboardState> = {};
        let eventLogs: TradeLog[] = [];

        switch (type) {
            case 'initial_state':
                // Handled specifically by updateFromInitialState
                break;

            case 'node_start':
                updates.activeNode = data.node;
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'info',
                    node: data.node,
                    message: `Started execution of ${data.node}`,
                    timestamp
                });
                break;

            case 'ai_thinking':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'thinking',
                    node: data.node,
                    message: data.message,
                    timestamp,
                    data: data.step
                });
                break;

            case 'analysis_complete':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'success',
                    node: data.node,
                    message: `Analysis complete: ${data.analysis.market_cycle}`,
                    timestamp,
                    data: data.analysis
                });
                break;

            case 'strategy_complete':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'decision',
                    node: data.node,
                    message: `Strategy generated: ${data.decision.operation}`,
                    timestamp,
                    data: data.decision
                });
                break;

            case 'market_data_complete':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'market_data',
                    node: data.node,
                    message: `Market data fetched successfully`,
                    timestamp,
                    data
                });
                break;

            case 'risk_assessment_complete':
                const plans = data.execution_plans || [];
                const planLogs = plans.map((plan: any) => ({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'plan',
                    node: 'risk',
                    message: `Risk Assessment: ${plan.operation} ${plan.symbol}`,
                    timestamp,
                    data: plan
                }));

                // Add risk summary log if summary data exists
                if (data.summary) {
                    planLogs.push({
                        id: Math.random().toString(36).substr(2, 9),
                        type: 'risk_summary',
                        node: 'risk',
                        message: `Risk summary`,
                        timestamp,
                        data: data.summary
                    });
                }
                eventLogs.push(...planLogs);
                break;

            case 'status_change':
                updates.status = data.status;
                break;

            case 'position_update':
                updates.trading = { ...get().trading, current_position: data };
                break;

            case 'error_added':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'error',
                    node: 'system',
                    message: data.error,
                    timestamp
                });
                break;

            case 'trade_update':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'trade',
                    node: 'execution',
                    message: `New trade recorded. PnL: ${data.pnl}`,
                    timestamp,
                    data
                });
                break;

            case 'market_update':
                if (data.price) {
                    const time = timestamp ? new Date(timestamp).getTime() / 1000 : Date.now() / 1000;
                    const roundedTime = Math.round(time * 1000) / 1000;
                    const price = { time: roundedTime, value: data.price };

                    if (isHistory) {
                        updates.prices = [price];
                    } else {
                        // For real-time, also ensure we don't duplicate or go backwards
                        const currentPrices = get().prices;
                        const lastPrice = currentPrices[currentPrices.length - 1];

                        if (!lastPrice || roundedTime > lastPrice.time) {
                            updates.prices = [...currentPrices, price].slice(-1000);
                        } else if (roundedTime === lastPrice.time) {
                            // Update last price if same timestamp
                            updates.prices = [...currentPrices.slice(0, -1), price];
                        }
                    }
                }
                break;

            case 'execution_complete':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'execution',
                    node: data.node,
                    message: `Execution: ${data.trade.side} ${data.trade.symbol} (${data.trade.status})`,
                    timestamp,
                    data: data.trade
                });
                break;

            case 'llm_log':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'llm_log',
                    node: data.node,
                    message: `LLM Interaction (${data.model})`,
                    timestamp,
                    data
                });
                break;

            case 'order_monitor_update':
                eventLogs.push({
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'monitor',
                    node: data.node,
                    message: `Order Monitor: ${data.status} ${data.order_id}`,
                    timestamp,
                    data
                });
                break;
        }

        // Handle logs accumulation/merge
        if (eventLogs.length > 0) {
            if (isHistory) {
                updates.logs = eventLogs;
            } else {
                updates.logs = [...eventLogs, ...get().logs].slice(0, 500);
            }
        }

        if (!isHistory) {
            set((state) => ({ ...state, ...updates }));
        }

        return updates;
    },

    addLog: (log) => set((state) => ({
        logs: [{ ...log, id: Math.random().toString(36).substr(2, 9) }, ...state.logs].slice(0, 500)
    })),

    setSystemStatus: (status) => set({ status }),

    updatePosition: (position) => set((state) => ({
        trading: { ...state.trading, current_position: position }
    })),

    setActiveNode: (node) => set({ activeNode: node }),

    addPrice: (price) => set((state) => {
        // Keep only last 1000 prices for the chart
        const newPrices = [...state.prices, price].slice(-1000);
        return { prices: newPrices };
    }),

    setView: (view) => set({ currentView: view }),

    fetchHistoryRuns: async (filters = {}) => {
        set({ historyLoading: true });
        try {
            const wsUrl = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws';
            const baseUrl = wsUrl.replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

            const params = new URLSearchParams();
            if (filters.start_date) params.append('start_date', filters.start_date);
            if (filters.end_date) params.append('end_date', filters.end_date);
            if (filters.symbol) params.append('symbol', filters.symbol);

            const response = await fetch(`${baseUrl}/history/runs?${params.toString()}`);
            const data = await response.json();
            set({ historyRuns: data.runs || [], historyLoading: false });
        } catch (error) {
            console.error('Failed to fetch history runs:', error);
            set({ historyRuns: [], historyLoading: false });
        }
    },

    fetchRunDetails: async (runId: string) => {
        set({ historyLoading: true });
        try {
            const wsUrl = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws';
            const baseUrl = wsUrl.replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

            const response = await fetch(`${baseUrl}/history/runs/${runId}`);
            const data = await response.json();
            set({ currentRunDetails: data, historyLoading: false });
        } catch (error) {
            console.error('Failed to fetch run details:', error);
            set({ historyLoading: false });
        }
    },

    fetchGraphStructure: async () => {
        set({ graphLoading: true });
        try {
            const wsUrl = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws';
            const baseUrl = wsUrl.replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

            const response = await fetch(`${baseUrl}/graph`);
            const data = await response.json();

            if (data.error) {
                console.error('Failed to fetch graph structure:', data.error);
                set({ graphData: null, graphLoading: false });
            } else {
                set({ graphData: data, graphLoading: false });
            }
        } catch (error) {
            console.error('Failed to fetch graph structure:', error);
            set({ graphData: null, graphLoading: false });
        }
    },
}));
