import { create } from 'zustand';
import { buildApiUrl } from './lib/api';
import { processDashboardEvent } from './store/eventProcessor';
import { createLogId, MAX_LOGS, MAX_PRICES } from './store/types';
import type { DashboardEvent, PricePoint, TradeLog } from './store/types';

interface GraphNode {
    id: string;
    label: string;
    subgraph?: string;
}

interface GraphEdge {
    id: string;
    source: string;
    target: string;
    conditional: boolean;
    label?: string;
}

interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
    subgraphs: string[];
}

interface TradingState {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    total_pnl: number;
    pnl_percentage: number;
    max_drawdown: number;
    drawdown_percent: number;
    current_position: any | null;
}

interface SafetyState {
    equity_protector: Record<string, unknown>;
    error_count: number;
    last_error: string | null;
}

interface HistoryFilters {
    start_date?: string;
    end_date?: string;
    symbol?: string;
}

interface DashboardState {
    status: string;
    system: any;
    trading: TradingState;
    performance: any;
    safety: SafetyState;
    logs: TradeLog[];
    activeNode: string | null;
    prices: PricePoint[];
    currentView: string;

    historyRuns: any[];
    currentRunDetails: any | null;
    historyLoading: boolean;

    graphData: GraphData | null;
    graphLoading: boolean;

    updateFromInitialState: (data: any) => void;
    addLog: (log: Omit<TradeLog, 'id'>) => void;
    setSystemStatus: (status: string) => void;
    updatePosition: (position: any) => void;
    setActiveNode: (node: string | null) => void;
    addPrice: (price: PricePoint) => void;
    setView: (view: string) => void;
    processEvent: (message: DashboardEvent, isHistory?: boolean) => Partial<DashboardState>;
    fetchHistoryRuns: (filters?: HistoryFilters) => Promise<void>;
    fetchRunDetails: (runId: string) => Promise<void>;
    fetchGraphStructure: () => Promise<void>;
}

const dedupeAndSortPrices = (rawPrices: PricePoint[]) => {
    const sorted = [...rawPrices].sort((a, b) => a.time - b.time);
    const seenTimes = new Set<number>();
    const finalPrices: PricePoint[] = [];

    for (const point of sorted) {
        const roundedTime = Math.round(point.time * 1000) / 1000;
        if (!seenTimes.has(roundedTime)) {
            finalPrices.push({ ...point, time: roundedTime });
            seenTimes.add(roundedTime);
        }
    }

    return finalPrices.slice(-MAX_PRICES);
};

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
        let accumulatedPrices: PricePoint[] = [];
        let replayStatus = data.system?.status || state.status;
        let replayActiveNode = state.activeNode;

        if (Array.isArray(data.history)) {
            for (const event of data.history) {
                const { updates } = processDashboardEvent({
                    message: event,
                    isHistory: true,
                    currentTrading: state.trading,
                    currentPrices: accumulatedPrices,
                    currentLogs: accumulatedLogs
                });

                if (updates.logs) {
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
            }
        }

        return {
            ...state,
            status: replayStatus,
            system: data.system || state.system,
            trading: data.trading || state.trading,
            performance: data.performance || state.performance,
            safety: data.safety || state.safety,
            logs: accumulatedLogs.slice(0, MAX_LOGS),
            prices: dedupeAndSortPrices(accumulatedPrices),
            activeNode: replayActiveNode
        };
    }),

    processEvent: (message, isHistory = false) => {
        const state = get();
        const { updates } = processDashboardEvent({
            message,
            isHistory,
            currentTrading: state.trading,
            currentPrices: state.prices,
            currentLogs: state.logs
        });

        if (!isHistory) {
            set((prev) => ({ ...prev, ...updates }));
        }

        return updates;
    },

    addLog: (log) => set((state) => ({
        logs: [{ ...log, id: createLogId() }, ...state.logs].slice(0, MAX_LOGS)
    })),

    setSystemStatus: (status) => set({ status }),

    updatePosition: (position) => set((state) => ({
        trading: { ...state.trading, current_position: position }
    })),

    setActiveNode: (node) => set({ activeNode: node }),

    addPrice: (price) => set((state) => {
        const next = [...state.prices, price].slice(-MAX_PRICES);
        return { prices: next };
    }),

    setView: (view) => set({ currentView: view }),

    fetchHistoryRuns: async (filters = {}) => {
        set({ historyLoading: true });
        try {
            const params = new URLSearchParams();
            if (filters.start_date) params.append('start_date', filters.start_date);
            if (filters.end_date) params.append('end_date', filters.end_date);
            if (filters.symbol) params.append('symbol', filters.symbol);

            const response = await fetch(buildApiUrl('/history/runs', params));
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
            const response = await fetch(buildApiUrl(`/history/runs/${runId}`));
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
            const response = await fetch(buildApiUrl('/graph'));
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
