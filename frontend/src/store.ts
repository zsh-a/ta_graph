import { create } from 'zustand';
import { processDashboardEvent } from './store/eventProcessor';
import { MAX_LOGS, MAX_PRICES } from './store/types';
import type { CandlePoint, DashboardEvent, TradeLog } from './store/types';

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

interface DashboardState {
    status: string;
    system: any;
    trading: TradingState;
    performance: any;
    safety: SafetyState;
    logs: TradeLog[];
    candles: CandlePoint[];
    market: {
        symbol: string;
        exchange: string;
        timeframe: string;
        current_price: number;
        price_change_24h: number;
    };

    updateFromInitialState: (data: any) => void;
    setSystemStatus: (status: string) => void;
    processEvent: (message: DashboardEvent, isHistory?: boolean) => Partial<DashboardState>;
}

const dedupeAndSortCandles = (rawCandles: CandlePoint[]) => {
    const sorted = [...rawCandles].sort((a, b) => a.time - b.time);
    const map = new Map<number, CandlePoint>();
    for (const candle of sorted) {
        const roundedTime = Math.round(candle.time);
        map.set(roundedTime, { ...candle, time: roundedTime });
    }
    return [...map.values()].slice(-MAX_PRICES);
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
    candles: [],
    market: {
        symbol: 'BTCUSDT',
        exchange: 'bitget',
        timeframe: '1h',
        current_price: 0,
        price_change_24h: 0
    },

    updateFromInitialState: (data) => set((state) => {
        let accumulatedLogs: TradeLog[] = [];
        let accumulatedCandles: CandlePoint[] = [];
        let replayStatus = data.system?.status || state.status;
        let replayMarket: DashboardState['market'] = state.market;

        if (Array.isArray(data.history)) {
            for (const event of data.history) {
                const { updates } = processDashboardEvent({
                    message: event,
                    isHistory: true,
                    currentTrading: state.trading,
                    currentLogs: accumulatedLogs
                });

                if (updates.logs) {
                    accumulatedLogs = [...updates.logs, ...accumulatedLogs];
                }
                if (updates.candles) {
                    accumulatedCandles = [...accumulatedCandles, ...updates.candles];
                }
                if (updates.status !== undefined) {
                    replayStatus = updates.status;
                }
                if (updates.market !== undefined) {
                    replayMarket = {
                        symbol: updates.market.symbol ?? replayMarket.symbol,
                        exchange: updates.market.exchange ?? replayMarket.exchange,
                        timeframe: updates.market.timeframe ?? replayMarket.timeframe,
                        current_price: updates.market.current_price ?? replayMarket.current_price,
                        price_change_24h: updates.market.price_change_24h ?? replayMarket.price_change_24h,
                    };
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
            candles: dedupeAndSortCandles(accumulatedCandles),
            market: replayMarket
        };
    }),

    processEvent: (message, isHistory = false) => {
        const state = get();
        const { updates } = processDashboardEvent({
            message,
            isHistory,
            currentTrading: state.trading,
            currentLogs: state.logs
        });

        const normalizedUpdates: Partial<DashboardState> = {
            ...updates,
            market: updates.market
                ? {
                    symbol: updates.market.symbol ?? state.market.symbol,
                    exchange: updates.market.exchange ?? state.market.exchange,
                    timeframe: updates.market.timeframe ?? state.market.timeframe,
                    current_price: updates.market.current_price ?? state.market.current_price,
                    price_change_24h: updates.market.price_change_24h ?? state.market.price_change_24h,
                }
                : undefined,
        };

        if (!isHistory) {
            set((prev) => ({ ...prev, ...normalizedUpdates }));
        }

        return normalizedUpdates;
    },
    setSystemStatus: (status) => set({ status }),
}));
