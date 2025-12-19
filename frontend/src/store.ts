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

    // Actions
    updateFromInitialState: (data: any) => void;
    addLog: (log: Omit<TradeLog, 'id'>) => void;
    setSystemStatus: (status: string) => void;
    updatePosition: (position: any) => void;
    setActiveNode: (node: string | null) => void;
    addPrice: (price: { time: number; value: number }) => void;
    setView: (view: string) => void;
    processEvent: (message: any, isHistory?: boolean) => Partial<DashboardState>;
}

export const useStore = create<DashboardState>((set, get) => ({
    status: 'offline',
    system: { heartbeat_count: 0, last_heartbeat: null },
    trading: { total_trades: 0, winning_trades: 0, losing_trades: 0, total_pnl: 0, current_position: null },
    performance: { recent_pnl: [], execution_times: [] },
    safety: { equity_protector: {}, error_count: 0, last_error: null },
    logs: [],
    activeNode: null,
    prices: [],
    currentView: 'cockpit',

    updateFromInitialState: (data) => set((state) => {
        // Re-process history events to populate logs and other state
        if (data.history && Array.isArray(data.history)) {
            // We need to clear current session-only state before replaying
            state.logs = [];
            data.history.forEach((event: any) => {
                state = { ...state, ...state.processEvent(event, true) };
            });
        }

        return {
            ...state,
            status: data.system.status,
            system: data.system,
            trading: data.trading,
            performance: data.performance,
            safety: data.safety,
        };
    }),

    processEvent: (message: any, isHistory = false) => {
        const { type, data, timestamp } = message;
        let updates: Partial<DashboardState> = {};

        switch (type) {
            case 'initial_state':
                // Handled specifically by updateFromInitialState
                break;

            case 'node_start':
                updates.activeNode = data.node;
                updates.logs = [{
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'info',
                    node: data.node,
                    message: `Started execution of ${data.node}`,
                    timestamp
                }, ...(isHistory ? [] : get().logs)].slice(0, 500);
                break;

            case 'ai_thinking':
                updates.logs = [{
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'thinking',
                    node: data.node,
                    message: data.message,
                    timestamp,
                    data: data.step
                }, ...(isHistory ? [] : get().logs)].slice(0, 500);
                break;

            case 'analysis_complete':
                updates.logs = [{
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'success',
                    node: data.node,
                    message: `Analysis complete: ${data.analysis.market_cycle}`,
                    timestamp,
                    data: data.analysis
                }, ...(isHistory ? [] : get().logs)].slice(0, 500);
                break;

            case 'strategy_complete':
                updates.logs = [{
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'decision',
                    node: data.node,
                    message: `Strategy generated: ${data.decision.operation}`,
                    timestamp,
                    data: data.decision
                }, ...(isHistory ? [] : get().logs)].slice(0, 500);
                break;

            case 'status_change':
                updates.status = data.status;
                break;

            case 'position_update':
                updates.trading = { ...get().trading, current_position: data };
                break;

            case 'error_added':
                updates.logs = [{
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'error',
                    node: 'system',
                    message: data.error,
                    timestamp
                }, ...(isHistory ? [] : get().logs)].slice(0, 500);
                break;

            case 'trade_update':
                updates.logs = [{
                    id: Math.random().toString(36).substr(2, 9),
                    type: 'trade',
                    node: 'execution',
                    message: `New trade recorded. PnL: ${data.pnl}`,
                    timestamp,
                    data
                }, ...(isHistory ? [] : get().logs)].slice(0, 500);
                break;

            case 'market_update':
                if (data.price) {
                    const price = { time: Date.now() / 1000, value: data.price };
                    updates.prices = [...get().prices, price].slice(-1000);
                }
                break;
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
}));
